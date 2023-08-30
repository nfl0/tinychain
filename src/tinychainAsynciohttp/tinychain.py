class Miner:
    def __init__(self, mempool, storage_engine, validation_engine, miner_address, last_block_data):
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.miner_address = miner_address
        self.running = True
        self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
        self.block_height = last_block_data['height'] + 1 if last_block_data else 0
        self.block_timer = None

    async def mine_block(self):
        while self.running:
            transactions_to_mine = self.mempool.get_transactions()
            valid_transactions_to_mine = []

            for transaction in transactions_to_mine:
                if self.validation_engine.validate_transaction(transaction):
                    valid_transactions_to_mine.append(transaction)
                else:
                    self.mempool.remove_transaction(transaction)

            transactions_to_include = valid_transactions_to_mine[:3]

            block = Block(self.block_height, transactions_to_include, self.miner_address, self.previous_block_hash)
            self.storage_engine.store_block(block)

            for transaction in transactions_to_include:
                self.mempool.remove_transaction(transaction)

            self.previous_block_hash = block.block_hash
            self.block_height += 1

            await asyncio.sleep(BLOCK_TIME)
