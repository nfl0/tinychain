import blake3
import time
from transaction import Transaction

class Block:
    def __init__(self, height, transactions, validator_address, previous_block_hash=None, timestamp=None):
        self.height = height
        self.transactions = transactions
        self.timestamp = timestamp or int(time.time())
        self.validator = validator_address
        self.previous_block_hash = previous_block_hash
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        sorted_transaction_hashes = sorted([t.to_dict()['transaction_hash'] for t in self.transactions])
        values = sorted_transaction_hashes + [str(self.timestamp)]
        if self.previous_block_hash:
            values.append(str(self.previous_block_hash))
        return blake3.blake3(''.join(values).encode()).hexdigest()
    
    @classmethod
    def from_dict(cls, block_data):
        height = block_data['height']
        transactions = [Transaction(**t) for t in block_data['transactions']]
        timestamp = block_data['timestamp']
        validator_address = block_data['validator']
        previous_block_hash = block_data['previous_block_hash']
        return cls(height, transactions, validator_address, previous_block_hash, timestamp)