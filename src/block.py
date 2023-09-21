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
        self.merkle_root = self.calculate_merkle_root()
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        values = [self.merkle_root, str(self.timestamp)]
        if self.previous_block_hash:
            values.append(str(self.previous_block_hash))
        concatenated_string = ''.join(values).encode()  # Encode to bytes
        return blake3.blake3(concatenated_string).hexdigest()

    def calculate_merkle_root(self):
        transaction_hashes = [t.to_dict()['transaction_hash'] for t in self.transactions]
        return self.compute_merkle_root(transaction_hashes)

    @staticmethod
    def compute_merkle_root(transaction_hashes):
        if len(transaction_hashes) == 0:
            return blake3.blake3(b'').hexdigest()

        while len(transaction_hashes) > 1:
            if len(transaction_hashes) % 2 != 0:
                transaction_hashes.append(transaction_hashes[-1])
            transaction_hashes = [blake3.blake3(transaction_hashes[i].encode() + transaction_hashes[i + 1].encode()).digest() for i in range(0, len(transaction_hashes), 2)]

        return blake3.blake3(transaction_hashes[0].encode()).hexdigest()


    @classmethod
    def from_dict(cls, block_data):
        height = block_data['height']
        transactions = [Transaction(**t) for t in block_data['transactions']]
        timestamp = block_data['timestamp']
        validator_address = block_data['validator']
        previous_block_hash = block_data['previous_block_hash']
        return cls(height, transactions, validator_address, previous_block_hash, timestamp)
