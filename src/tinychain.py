from flask import Flask, request, jsonify
import threading
import time
import blake3
import logging
import signal
import sys

app = Flask(__name__)

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def validate_transaction(self, transaction):
        sender_address = transaction.get('sender')
        receiver_address = transaction.get('receiver')
        amount = transaction.get('amount')

        if not all([sender_address, receiver_address, amount]):
            return False  # Transaction data is incomplete

        sender_balance = self.storage_engine.fetch_balance(sender_address)
        if sender_balance is None or sender_balance < amount + 1:
            return False  # Insufficient balance

        return True

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
                    transactions_to_process = [transaction]  # Placeholder, you might accumulate multiple transactions
                    block = self.create_block(transactions_to_process)
                    self.storage_engine.store_block(block)
                    logging.info(f"Added transaction '{transaction}' to a new block and stored the block.")
            else:
                block = self.create_block([])  # Create empty block with timestamp
                self.storage_engine.store_block(block)
                logging.info("Created an empty block.")

            time.sleep(5)  # Wait for 5 seconds

    def create_block(self, transactions):
        timestamp = int(time.time())  # Unix timestamp
        block_data = {
            "timestamp": timestamp,
            "transactions": transactions,
        }
        block_hash = self.generate_block_hash(block_data)
        block_data["block_hash"] = block_hash
        return block_data

    def generate_block_hash(self, block_data):
        # Use blake3 to generate a block hash based on block data
        hasher = blake3.blake3()
        for key, value in block_data.items():
            hasher.update(str(value).encode())
        return hasher.hexdigest()

class StorageEngine:
    def store_block(self, block):
        # Placeholder implementation, store block data in database
        logging.info(f"Stored block: {block}")

    def fetch_balance(self, account_address):
        # Placeholder implementation, retrieve account balance from database
        # Replace this with your actual database retrieval logic
        return None

def handle_shutdown(signum, frame):
    logging.info("Shutting down gracefully...")
    miner.running = False
    flask_thread.join()  # Wait for the Flask thread to finish
    sys.exit(0)

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
    if 'transaction' in data:
        transaction = data['transaction']
        if validation_engine.validate_transaction(transaction):
            mempool.add_transaction(transaction)
            return jsonify({'message': 'Transaction added to mempool'})
        else:
            return jsonify({'error': 'Invalid transaction'})
    else:
        return jsonify({'error': 'Transaction data not provided'})

@app.route('/get_block/<block_hash>', methods=['GET'])
def get_block(block_hash):
    block_data = storage_engine.fetch_block(block_hash)
    return jsonify(block_data)

@app.route('/balance/<account_address>', methods=['GET'])
def get_balance(account_address):
    balance_data = storage_engine.fetch_balance(account_address)
    return jsonify(balance_data)

if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.start()

    # Start the miner thread
    miner.start()

    # Register the shutdown handler for SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Remove the infinite loop
    try:
        flask_thread.join()  # Wait for the Flask thread to finish
        miner.join()  # Wait for the miner thread to finish
    except KeyboardInterrupt:
        handle_shutdown(signal.SIGINT, None)  # Trigger the shutdown handler