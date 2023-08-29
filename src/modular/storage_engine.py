import plyvel
import json
import logging

class StorageEngine:
    def __init__(self, block_reward):
        self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
        self.db_accounts = plyvel.DB('accounts.db', create_if_missing=True)
        self.last_block_hash = None
        self.block_reward = block_reward

    def store_block(self, block):
        block_data = {
            'height': block.height,
            'transactions': block.transactions,
            'timestamp': block.timestamp,
            'miner': block.miner,
            'block_hash': block.block_hash,
            'previous_block_hash': block.previous_block_hash
        }
        self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data).encode())
        
        # Update miner account balance with block reward
        miner_balance = self.fetch_balance(block.miner)
        if miner_balance is None:
            self.db_accounts.put(block.miner.encode(), str(0).encode())
        if miner_balance is not None:
            self.db_accounts.put(block.miner.encode(), str(miner_balance + self.block_reward).encode())

        # Update account balances for transactions
        for transaction in block.transactions:
            sender = transaction['sender']
            receiver = transaction['receiver']
            amount = transaction['amount']
            sender_balance = self.fetch_balance(sender)
            if sender_balance is not None:
                self.db_accounts.put(sender.encode(), str(sender_balance - amount).encode())
            receiver_balance = self.fetch_balance(receiver)
            if receiver_balance is None:
                self.db_accounts.put(receiver.encode(), str(0).encode())
                receiver_balance = 0
            receiver_balance += amount
            self.db_accounts.put(receiver.encode(), str(receiver_balance).encode())

        self.last_block_hash = block.block_hash

        logging.info(f"Stored block: {block.block_hash}")

    def fetch_balance(self, account_address):
        balance = self.db_accounts.get(account_address.encode())
        if balance is not None:
            return int(balance.decode())
        return None

    def fetch_block(self, block_hash):
        block_data = self.db_blocks.get(block_hash.encode())
        if block_data is not None:
            return json.loads(block_data.decode())
        return None
    
    def fetch_last_block(self):
        last_block = None
        for block_hash, block_data in self.db_blocks.iterator(reverse=True):
            block_info = json.loads(block_data.decode())
            if last_block is None or block_info['height'] > last_block['height']:
                last_block = block_info
        return last_block
    
    def close(self):
        self.db_blocks.close()
        self.db_accounts.close()