import logging
from parameters import BLOCK_REWARD
from merkle_tree import MerkleTree

tinycoin = 1000000000000000000  # 1 tinycoin = 1000000000000000000 tatoshi
genesis_addresses = [
    "374225f9043c475981d2da0fd3efbe6b8e382bb3802c062eacfabe5e0867052238ed6acaf99c5c33c1cce1a3e1ef757efd9c857417f26e2e1b5d9ab9e90c9b4d",
    "50c43f64ba255a95ab641978af7009eecef03610d120eb35035fdb0ea3c1b7f05859382f117ff396230b7cb453992d3b0da1c03f8a0572086eb938862bf6d77e",
]


class TinyVMEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine
        self.merkle_tree = MerkleTree()

        # Initialize the contract state cache
        self.contract_state_cache = {}

        ### System Contracts ###
        self.accounts_contract_address = "6163636f756e7473"
        self.staking_contract_address = "7374616b696e67"  # the word 'staking' in hex
        self.storage_contract_address = "73746f72616765"  # the word'storage' in hex
        ### End of System SCs ###

    def exec(self, transactions, validator):
        
        # Fetch the accounts contract state from cache or storage
        accounts_contract_state = self.get_contract_state(
            self.accounts_contract_address
        )
        staking_contract_state = self.get_contract_state(self.staking_contract_address)

        # Update validator account balance with block reward
        self.execute_accounts_contract(
            accounts_contract_state, validator, None, BLOCK_REWARD, "credit"
        )

        for transaction in transactions:
            sender, receiver, amount, memo = (
                transaction.sender,
                transaction.receiver,
                transaction.amount,
                transaction.memo,
            )

            self.execute_accounts_contract(
                accounts_contract_state, sender, receiver, amount, "transfer"
            )

            if receiver == self.staking_contract_address:
                if memo in ("stake", "unstake"):
                    # accept memo = {unstake, amount}
                    staking_contract_state = self.get_contract_state(
                        self.staking_contract_address
                    )
                    is_stake = memo == "stake"
                    self.execute_staking_contract(
                        staking_contract_state, sender, amount, is_stake
                    )
                else:
                    logging.info("TinyVM: (main): Invalid memo. Try 'stake' or 'unstake'")

        # Calculate the Merkle root
        state = {
            self.accounts_contract_address: accounts_contract_state,
            self.staking_contract_address: staking_contract_state,
        }
        state_root = self.merkle_tree.root_hash().hex()
        return state_root, state

    def execute_accounts_contract(
        self, contract_state, sender, receiver, amount, operation
    ):
        if contract_state is None:
            contract_state = {}
            contract_state[sender] = 2002*tinycoin # the "genesis" account balance to be exhausted within genesis
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
                # show logging.info that says the sender send the amount to the receiver
                logging.info(f"TinyVM: (accounts contract): {receiver} received {amount} from {sender}")
            else:
                logging.info(f"TinyVM: (accounts contract): Insufficient balance for sender: {sender}")

        # Update contract state in cache
        self.contract_state_cache[self.accounts_contract_address] = contract_state
        self.merkle_tree.append(bytes(str(contract_state), "utf-8"))

    def execute_staking_contract(self, contract_state, sender, amount, operation):
        if contract_state is None:
            contract_state = {}
        staked_balance = contract_state.get(sender, 0)
        if operation:
            new_staked_balance = staked_balance + amount
            contract_state[sender] = new_staked_balance
            logging.info(
                f"TinyVM (staking contract): {sender} staked {amount} tinycoins for contract {self.staking_contract_address}. New staked balance: {new_staked_balance}"
            )
        else:
            if staked_balance > 0:
                released_balance = staked_balance
                contract_state[sender] = 0
                self.execute_accounts_contract(
                    self.get_contract_state(self.accounts_contract_address),
                    self.staking_contract_address,
                    sender,
                    released_balance,
                    "transfer",
                )

                logging.info(
                    f"TinyVM (staking contract): {sender} unstaked {released_balance} tinycoins for contract {self.staking_contract_address}. Staked balance reset to zero."
                )
            else:
                logging.info(
                    f"TinyVM (staking contract): {sender} has no staked tinycoins for contract {self.staking_contract_address} to unstake."
                )

        # Update contract state in cache
        self.contract_state_cache[self.staking_contract_address] = contract_state
        self.merkle_tree.append(bytes(str(contract_state), "utf-8"))

    def get_contract_state(self, contract_address):
        if contract_address in self.contract_state_cache:
            return self.contract_state_cache[contract_address]
        else:
            # Fetch contract state from storage engine
            contract_state = self.storage_engine.fetch_contract_state(contract_address)

            # Store it in the cache
            self.contract_state_cache[contract_address] = contract_state

            return contract_state
