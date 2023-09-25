import logging
from parameters import BLOCK_REWARD
from merkle_tree import MerkleTree

class TinyVMEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine
        self.merkle_tree = MerkleTree()
        self.contract_state_cache = {}
        self.system_contracts = {
            "accounts": "6163636f756e7473",
            "staking": "7374616b696e67",  # the word 'staking' in hex
            "storage": "73746f72616765",  # the word 'storage' in hex
        }

    def execute_block(self, block):
        accounts_contract_state = self.get_contract_state(self.system_contracts["accounts"])
        staking_contract_state = None
        
        for transaction in block.transactions:
            sender, receiver, amount, memo = (
                transaction.sender,
                transaction.receiver,
                transaction.amount,
                transaction.memo,
            )

            self.execute_accounts_contract(accounts_contract_state, sender, receiver, amount, "transfer")

            if receiver == self.system_contracts["staking"]:
                if memo in ("stake", "unstake"):
                    staking_contract_state = self.get_contract_state(self.system_contracts["staking"])
                    is_stake = memo == "stake"
                    self.execute_staking_contract(staking_contract_state, sender, receiver, amount, is_stake)
                else:
                    logging.info("Invalid memo. Try 'stake' or 'unstake'")

        # Check if self.merkle_tree is not None before calculating the Merkle root
        if self.merkle_tree is not None:
            root_hash = self.merkle_tree.root_hash()
            if root_hash is not None:
                state_root = root_hash.hex()
                if block.state_root is None or state_root == block.state_root:
                    block.state_root = state_root
                    self.store_contract_state(self.system_contracts["accounts"], accounts_contract_state)
                    if staking_contract_state is not None:
                        self.store_contract_state(self.system_contracts["staking"], staking_contract_state)
                    return True
                else:
                    logging.info("Invalid state root")
                    return False
            else:
                logging.info("Merkle tree root hash is None")
                return False
        else:
            logging.info("Merkle tree is not initialized")
            return False


    def execute_accounts_contract(self, contract_state, sender, receiver, amount, operation):
        if contract_state is None:
            contract_state = {}
        if operation == "credit":
            contract_state[sender] = contract_state.get(sender, 0) + amount
        elif operation == "transfer":
            sender_balance = contract_state.get(sender, 0)
            if sender_balance >= amount:
                contract_state[sender] = sender_balance - amount
                contract_state[receiver] = contract_state.get(receiver, 0) + amount
            else:
                logging.info(f"Insufficient balance for sender: {sender}")

        self.update_contract_state_cache(self.system_contracts["accounts"], contract_state)

    def execute_staking_contract(self, contract_state, sender, receiver, amount, operation):
        if contract_state is None:
            contract_state = {}
        staked_balance = contract_state.get(sender, 0)
        if operation:
            contract_state[sender] = staked_balance + amount
            logging.info(
                f"{sender} staked {amount} tinycoins for contract {self.system_contracts['staking']}. New staked balance: {contract_state[sender]}"
            )
        else:
            if staked_balance > 0:
                released_balance = staked_balance
                contract_state[sender] = 0
                self.execute_accounts_contract(self.get_contract_state(self.system_contracts["accounts"]), receiver, sender, released_balance, "transfer")
                logging.info(
                    f"{sender} unstaked {released_balance} tinycoins for contract {self.system_contracts['staking']}. Staked balance reset to zero."
                )
            else:
                logging.info(
                    f"{sender} has no staked tinycoins for contract {self.system_contracts['staking']} to unstake."
                )

        self.update_contract_state_cache(self.system_contracts["staking"], contract_state)

    def get_contract_state(self, contract_address):
        if contract_address in self.contract_state_cache:
            return self.contract_state_cache[contract_address]
        else:
            contract_state = self.storage_engine.fetch_contract_state(contract_address)
            self.contract_state_cache[contract_address] = contract_state
            return contract_state

    def store_contract_state(self, contract_address, state_data):
        self.storage_engine.store_contract_state(contract_address, state_data)

    def update_contract_state_cache(self, contract_address, contract_state):
        self.contract_state_cache[contract_address] = contract_state
        self.merkle_tree.append(bytes(str(contract_state), "utf-8"))
