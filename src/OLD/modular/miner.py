import threading
from block import Block

class Miner(threading.Thread):
    def __init__(self, mempool, storage_engine, validation_engine, miner_address, last_block_data, block_time):
        super().__init__()
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.miner_address = miner_address
        self.running = True
        self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
        self.block_height = last_block_data['height'] + 1 if last_block_data else 0
        self.block_timer = None
        self.block_time = block_time

    def mine_block(self):
        transactions_to_mine = []
        while len(transactions_to_mine) < 3 and not self.mempool.is_empty():
            transaction = self.mempool.get_transaction()
            if self.validation_engine.validate_transaction(transaction):
                transactions_to_mine.append(transaction)

        block = Block(self.block_height, transactions_to_mine, self.miner_address, self.previous_block_hash)
        self.storage_engine.store_block(block)

        self.previous_block_hash = block.block_hash
        self.block_height += 1

        self.block_timer = threading.Timer(self.block_time, self.mine_block)  # Use self.block_time
        self.block_timer.start()


    def run(self):
        self.block_timer = threading.Timer(0, self.mine_block)
        self.block_timer.start()

    def stop(self):
        self.block_timer.cancel()
        self.running = False