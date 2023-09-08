import blake3
import time

class Block:
    def __init__(self, height, transactions, validator_address, previous_block_hash=None, timestamp=None):
        self.height = height
        self.transactions = transactions
        self.timestamp = timestamp or int(time.time())
        self.validator = validator_address
        self.previous_block_hash = previous_block_hash
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        sorted_transaction_hashes = sorted([t.transaction_hash for t in self.transactions])
        values = sorted_transaction_hashes + [str(self.timestamp)]
        if self.previous_block_hash:
            values.append(str(self.previous_block_hash))
        return blake3.blake3(''.join(values).encode()).hexdigest()