import blake3
import time

class Block:
    def __init__(self, height, transactions, miner_address, previous_block_hash=None):
        self.height = height
        self.transactions = transactions
        self.timestamp = int(time.time())
        self.miner = miner_address
        self.previous_block_hash = previous_block_hash
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        hasher = blake3.blake3()
        for transaction in self.transactions:
            hasher.update(str(transaction).encode())
        hasher.update(str(self.timestamp).encode())
        if self.previous_block_hash:
            hasher.update(str(self.previous_block_hash).encode())
        return hasher.hexdigest()