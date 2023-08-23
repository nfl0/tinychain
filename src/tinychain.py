from flask import Flask, request, jsonify
import threading
import time
import blake3
import logging
import ecdsa
from ecdsa import VerifyingKey


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
        self.transactions = []
        self.lock = threading.Lock()

    def add_transaction(self, transaction):
        with self.lock:
            self.transactions.append(transaction)

class Miner(threading.Thread):
    def __init__(self, mempool, storage_engine, validation_engine):
        super().__init__()
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.running = True

    def run(self):
        while self.running:
            if self.mempool.transactions:
                transaction = self.mempool.transactions.pop(0)
                if self.validation_engine.validate_transaction(transaction):
                    block = Block([transaction])
                    self.storage_engine.store_block(block)
                    logging.info(f"Added transaction '{transaction}' to a new block and stored the block.")
            else:
                block = Block([])  # Create empty block with timestamp
                self.storage_engine.store_block(block)
                logging.info("Created an empty block.")

            time.sleep(5)  # Wait for 5 seconds

class StorageEngine:
    def store_block(self, block):
        logging.info(f"Stored block: {block.block_hash}")

    def fetch_balance(self, account_address):
        # Placeholder implementation, retrieve account balance from database
        # Replace this with your actual database retrieval logic
        #return None
        return 100
    
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

if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.start()

    # Start the miner thread
    miner.start()

    try:
        while True:
            pass  # Keep the main thread running
    except KeyboardInterrupt:
        miner.running = False
        miner.join()  # Wait for the miner thread to finish
        flask_thread.join()  # Wait for the Flask thread to finish
