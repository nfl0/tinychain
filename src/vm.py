import logging
from parameters import BLOCK_REWARD

class TinyVMEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine
        ### System Contracts ###
        self.accounts_contract_address = "6163636f756e7473"
        self.staking_contract_address = "7374616b696e67"
        ### End of System SCs ###

    def execute_block(self, block):
        # Fetch the accounts contract state from storage
        accounts_contract_state = self.storage_engine.fetch_contract_state(self.accounts_contract_address)

        # Update validator account balance with block reward
        self.execute_accounts_contract(accounts_contract_state, block.validator, None, BLOCK_REWARD, "credit")

        for transaction in block.transactions:
            sender, receiver, amount, memo = (
                transaction.sender,
                transaction.receiver,
                transaction.amount,
                transaction.memo,
            )

            self.execute_accounts_contract(accounts_contract_state, sender, receiver, amount, "transfer")

            if receiver == self.staking_contract_address:
                if memo in ("stake", "unstake"):
                    staking_contract_state = self.storage_engine.fetch_contract_state(self.staking_contract_address)
                    is_stake = memo == "stake"
                    self.execute_staking_contract(staking_contract_state, sender, amount, is_stake)
                else:
                    logging.info("Invalid memo. Try 'stake' or 'unstake'")

    def execute_accounts_contract(self, contract_state, sender, receiver, amount, operation):
        if contract_state is None:
            contract_state = {}
        if operation == "credit":
            current_balance = contract_state.get(sender, 0)
            new_balance = current_balance + amount
            contract_state[sender] = new_balance
        elif operation == "transfer":
            sender_balance = contract_state.get(sender, 0)
            receiver_balance = contract_state.get(receiver, 0)
            if sender_balance >= amount:
                contract_state[sender] = sender_balance - amount
                contract_state[receiver] = receiver_balance + amount
            else:
                logging.info(f"Insufficient balance for sender: {sender}")

        self.store_contract_state(self.accounts_contract_address, contract_state)

    def execute_staking_contract(self, contract_state, sender, amount, operation):
        if contract_state is None:
            contract_state = {}
        staked_balance = contract_state.get(sender, 0)
        if operation:
            new_staked_balance = staked_balance + amount
            contract_state[sender] = new_staked_balance
            logging.info(
                f"{sender} staked {amount} tinycoins for contract {self.staking_contract_address}. New staked balance: {new_staked_balance}"
            )
        else:
            if staked_balance > 0:
                released_balance = staked_balance
                contract_state[sender] = 0
                self.execute_accounts_contract(contract_state, sender, None, released_balance, "credit")
                logging.info(
                    f"{sender} unstaked {released_balance} tinycoins for contract {self.staking_contract_address}. Staked balance reset to zero."
                )
            else:
                logging.info(
                    f"{sender} has no staked tinycoins for contract {self.staking_contract_address} to unstake."
                )

        self.store_contract_state(self.staking_contract_address, contract_state)

    def get_contract_state(self, contract_address):
        return self.storage_engine.fetch_contract_state(contract_address)

    def store_contract_state(self, contract_address, state_data):
        self.storage_engine.store_contract_state(contract_address, state_data)