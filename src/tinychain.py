from flask import Flask, request, jsonify
import threading
import time
import blake3
import logging
import ecdsa
from ecdsa import VerifyingKey
from queue import Queue
import atexit
import plyvel
import json

app = Flask(__name__)

BLOCK_TIME = 5
BLOCK_REWARD = 10
miner_public_key = 'aa9cbc6fe2966cd9343aab811e38cdfea9364c6563bf4939015f700d15c629a381af89af25ea29beb073c695f155f6d22abd1c864f8339e7f3536e88c2c6b98c'

class Block:
    def __init__(self, transactions, miner_address, previous_block_hash=None):
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

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def validate_transaction(self, transaction):
        required_fields = ['sender', 'receiver', 'amount', 'signature']
        if all(field in transaction for field in required_fields):
            sender_balance = self.storage_engine.fetch_balance(transaction['sender'])
            if sender_balance is not None and sender_balance >= transaction['amount']:
                if self.verify_transaction_signature(transaction):
                    return True
        return False

    def verify_transaction_signature(self, transaction):
        public_key = transaction['sender']
        signature = transaction['signature']
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=ecdsa.SECP256k1)
        try:
            vk.verify(bytes.fromhex(signature), transaction['message'].encode())
            return True
        except ecdsa.BadSignatureError:
            return False

class Mempool:
    def __init__(self):
        self.transactions = Queue()
    def add_transaction(self, transaction):
        self.transactions.put(transaction)
    def get_transaction(self):
        return self.transactions.get()
    def is_empty(self):
        return self.transactions.empty()

class Miner(threading.Thread):
    def __init__(self, mempool, storage_engine, validation_engine, miner_address):
        super().__init__()
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.miner_address = miner_address
        self.running = True
        self.previous_block_hash = None

    def initialize_account(self, account_address, initial_balance):
        if self.storage_engine.fetch_balance(account_address) is None:
            self.storage_engine.db_accounts.put(account_address.encode(), str(int(initial_balance)).encode())
            return True
        return False
    
    def run(self):
        while self.running:
            transactions_to_mine = []
            while len(transactions_to_mine) < 3 and not self.mempool.is_empty():
                transaction = self.mempool.get_transaction()
                if self.validation_engine.validate_transaction(transaction):
                    remaining_amount = transaction['amount']
                    if remaining_amount >= 0:
                        if not self.initialize_account(transaction['receiver'], remaining_amount):
                            transactions_to_mine.append(transaction)

            block = Block(transactions_to_mine, self.miner_address, self.previous_block_hash)
            self.storage_engine.store_block(block)

            self.previous_block_hash = block.block_hash  # Update previous block hash

            time.sleep(BLOCK_TIME)

class StorageEngine:
    def __init__(self):
        self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
        self.db_accounts = plyvel.DB('accounts.db', create_if_missing=True)
        self.last_block_hash = None

    def store_block(self, block):
        block_data = {
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
            self.db_accounts.put(block.miner.encode(), str(miner_balance + BLOCK_REWARD).encode())

        # Update account balances for transactions
        for transaction in block.transactions:
            sender = transaction['sender']
            receiver = transaction['receiver']
            amount = transaction['amount']
            sender_balance = self.fetch_balance(sender)
            if sender_balance is not None:
                self.db_accounts.put(sender.encode(), str(sender_balance - amount).encode())
            receiver_balance = self.fetch_balance(receiver)
            if receiver_balance is not None:
                new_receiver_balance = receiver_balance + amount
                self.db_accounts.put(receiver.encode(), str(new_receiver_balance).encode())

        self.last_block_hash = block.block_hash  # Update last block hash

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
    
    def close(self):
        self.db_blocks.close()
        self.db_accounts.close()
    
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
validation_engine = ValidationEngine(storage_engine)
mempool = Mempool()
miner = Miner(mempool, storage_engine, validation_engine, miner_public_key)

# API endpoints
@app.route('/send_transaction', methods=['POST'])
def send_transaction():
    data = request.json
    if 'transaction' in data and validation_engine.validate_transaction(data['transaction']):
        transaction = data['transaction']
        try:
            transaction['amount'] = int(transaction['amount'])
        except ValueError:
            return jsonify({'error': 'Invalid transaction amount'}), 400
        transaction['message'] = f"{transaction['sender']}-{transaction['receiver']}-{transaction['amount']}"
        mempool.add_transaction(transaction)
        return jsonify({'message': 'Transaction added to mempool'})
    return jsonify({'error': 'Invalid transaction data'}), 400

@app.route('/get_block/<string:block_hash>', methods=['GET'])
def get_block_by_hash(block_hash):
    block_data = storage_engine.fetch_block(block_hash)
    if block_data is not None:
        return jsonify(block_data)
    return jsonify({'error': 'Block not found'}), 404


stop_event = threading.Event()
def cleanup():
    stop_event.set()
    miner.join()
    flask_thread.join()
    storage_engine.close()
atexit.register(cleanup)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.start()

    miner.start()

    stop_event.wait()