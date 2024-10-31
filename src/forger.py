import time
import blake3
from block import BlockHeader, Signature
from wallet import Wallet

class Forger:
    def __init__(self, storage_engine, validation_engine, wallet):
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.wallet = wallet
        self.current_proposer_index = 0

    def fetch_current_validator_set(self):
        staking_contract_state = self.storage_engine.fetch_contract_state("7374616b696e67")
        if staking_contract_state:
            return sorted(staking_contract_state.keys(), key=lambda k: staking_contract_state[k]['index'])
        return []

    def select_proposer(self):
        validator_set = self.fetch_current_validator_set()
        if validator_set:
            proposer = validator_set[self.current_proposer_index]
            self.current_proposer_index = (self.current_proposer_index + 1) % len(validator_set)
            return proposer
        return None

    def validate_block(self, block_header):
        if not self.validation_engine.validate_block_header_signatures(block_header):
            return False
        if not self.validation_engine.validate_enough_signatures(block_header, required_signatures=2/3 * len(self.fetch_current_validator_set())):
            return False
        return True

    def forge_new_block(self, transactions, previous_block_header):
        proposer = self.select_proposer()
        if proposer == self.wallet.get_address():
            timestamp = int(time.time())
            state_root = self.storage_engine.compute_state_root(transactions)
            merkle_root = self.compute_merkle_root(transactions)
            block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_header.block_hash)
            signature = self.wallet.sign_message(block_hash)
            validator_index = self.get_validator_index(proposer)
            signatures = [Signature(proposer, timestamp, signature, validator_index)]

            block_header = BlockHeader(
                block_hash,
                previous_block_header.height + 1,
                timestamp,
                previous_block_header.block_hash,
                merkle_root,
                state_root,
                proposer,
                signatures,
                [tx.transaction_hash for tx in transactions]
            )

            if self.validate_block(block_header):
                self.storage_engine.store_block_header(block_header)
                self.storage_engine.store_state(state_root, self.storage_engine.compute_new_state(transactions))
                return block_header
        return None

    def generate_block_hash(self, merkle_root, timestamp, state_root, previous_block_hash):
        values = [merkle_root, str(timestamp), str(state_root), previous_block_hash]
        concatenated_string = f"{''.join(values)}".encode()
        return blake3.blake3(concatenated_string).hexdigest()

    def compute_merkle_root(self, transactions):
        transaction_hashes = [tx.transaction_hash for tx in transactions]
        if len(transaction_hashes) == 0:
            return blake3.blake3(b'').hexdigest()

        while len(transaction_hashes) > 1:
            if len(transaction_hashes) % 2 != 0:
                transaction_hashes.append(transaction_hashes[-1])
            transaction_hashes = [blake3.blake3(transaction_hashes[i].encode() + transaction_hashes[i + 1].encode()).digest() for i in range(0, len(transaction_hashes), 2)]

        return blake3.blake3(transaction_hashes[0]).hexdigest()

    def get_validator_index(self, validator_address):
        staking_contract_state = self.storage_engine.fetch_contract_state("7374616b696e67")
        if staking_contract_state and validator_address in staking_contract_state:
            return staking_contract_state[validator_address]['index']
        return -1
