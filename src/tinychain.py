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

class Block:
    def __init__(self, transactions):
        self.transactions = transactions
        self.timestamp = int(time.time())
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        hasher = blake3.blake3()
        for transaction in self.transactions:
            hasher.update(str(transaction).encode())
        hasher.update(str(self.timestamp).encode())
        return hasher.hexdigest()

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def validate_transaction(self, transaction):
        required_fields = ['sender', 'receiver', 'amount', 'signature']
        if all(field in transaction for field in required_fields):
            sender_balance = self.storage_engine.fetch_balance(transaction['sender'])
            if sender_balance is not None and sender_balance >= transaction['amount'] + 1:
                if transaction['message'] == 'block_reward':
                    return True
                elif self.verify_transaction_signature(transaction):
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
    def __init__(self, mempool, storage_engine, validation_engine):
        super().__init__()
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.running = True

    def run(self):
        while self.running:
            miner_public_key = '99628359a19dcba4c0400423478c3006d6fbcc8d0c0564db8d6cca5d4dfad7aaadf648e5d677ebc82a31d0c8045bd094a25b6f6984806638ac0b29fcfdb509d6'
            if not self.mempool.is_empty():
                # Mine transactions from mempool up to 3 transactions per block
                transactions_to_mine = []
                while len(transactions_to_mine) < 3 and not self.mempool.is_empty():
                    transaction = self.mempool.get_transaction()
                    if self.validation_engine.validate_transaction(transaction):
                        transactions_to_mine.append(transaction)

                # Add block reward transaction
                block_reward_transaction = {
                    'sender': 'blockchain',
                    'receiver': miner_public_key,
                    'amount': 10,
                    'signature': '',
                    'message': 'block_reward'
                }
                transactions_to_mine.append(block_reward_transaction)

                block = Block(transactions_to_mine)
                self.storage_engine.store_block(block)
                logging.info(f"Added {len(transactions_to_mine)} transactions to a new block and stored the block.")
            else:
                # Add block reward transaction
                block_reward_transaction = {
                    'sender': 'blockchain',
                    'receiver': miner_public_key,
                    'amount': 10,
                    'signature': '',
                    'message': 'block_reward'
                }
                block = Block([block_reward_transaction])  # Create empty block with timestamp
                self.storage_engine.store_block(block)
                logging.info("Created an empty block.")

            time.sleep(5)  # Wait for 5 seconds

class StorageEngine:
    def __init__(self):
        self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
        self.db_accounts = plyvel.DB('accounts.db', create_if_missing=True)

    def store_block(self, block):
        block_data = {
            'transactions': block.transactions,
            'timestamp': block.timestamp,
            'block_hash': block.block_hash
        }
        self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data).encode())

        # Update account balances
        for transaction in block.transactions:
            sender = transaction['sender']
            receiver = transaction['receiver']
            amount = transaction['amount']
            
            # Update sender's balance
            sender_balance = self.fetch_balance(sender)
            if sender_balance is not None:
                self.db_accounts.put(sender.encode(), str(sender_balance - amount - 1).encode())
            
            # Update receiver's balance
            receiver_balance = self.fetch_balance(receiver)
            if receiver_balance is not None:
                self.db_accounts.put(receiver.encode(), str(receiver_balance + amount).encode())

        logging.info(f"Stored block: {block.block_hash}")

    def fetch_balance(self, account_address):
        balance = self.db_accounts.get(account_address.encode())
        if balance is not None:
            return int(balance)
        return None
    
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
validation_engine = ValidationEngine(storage_engine)
mempool = Mempool()
miner = Miner(mempool, storage_engine, validation_engine)

# Define API endpoints
@app.route('/send_transaction', methods=['POST'])
def send_transaction():
    data = request.json
    if 'transaction' in data and validation_engine.validate_transaction(data['transaction']):
        transaction = data['transaction']
        transaction['message'] = f"{transaction['sender']}-{transaction['receiver']}-{transaction['amount']}"
        mempool.add_transaction(transaction)
        return jsonify({'message': 'Transaction added to mempool'})
    return jsonify({'error': 'Invalid transaction data'})

# Define an event to signal threads to stop
stop_event = threading.Event()

# Define a cleanup function to stop threads
def cleanup():
    stop_event.set()
    miner.join()  # Wait for the miner thread to finish
    flask_thread.join()  # Wait for the Flask thread to finish

# Register the cleanup function to be called on program exit
atexit.register(cleanup)

if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.start()

    # Start the miner thread
    miner.start()

    # Wait for the stop event
    stop_event.wait()