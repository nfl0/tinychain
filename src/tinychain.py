from flask import Flask, request, jsonify
import threading
import time
import random
import blake3  # Ensure you have installed blake3-py using 'pip install blake3'

app = Flask(__name__)

class ValidationEngine:
    def validate_transaction(self, transaction):
        # Placeholder implementation, perform validation checks
        # Example: Check sender's balance, verify signature, etc.
        transaction_valid = True
        if transaction_valid:
            return True
        else:
            return False

class Mempool:
    def __init__(self):
        self.transactions = []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

class Miner(threading.Thread):
    def __init__(self, mempool, storage_engine):
        super().__init__()
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.running = True

    def run(self):
        while self.running:
            if self.mempool.transactions:
                transaction = self.mempool.transactions.pop(0)
                if validation_engine.validate_transaction(transaction):
                    block = self.create_block([transaction])
                    self.storage_engine.store_block(block)
                    print(f"Added transaction '{transaction}' to a new block and stored the block.")
            time.sleep(5)  # Wait for 5 seconds

    def create_block(self, transactions):
        # Placeholder implementation, create a new block
        block = {
            "transactions": transactions,
            "block_hash": self.generate_block_hash(transactions)
        }
        return block

    def generate_block_hash(self, transactions):
        # Use blake3 to generate a block hash based on transactions
        hasher = blake3.blake3()
        for transaction in transactions:
            hasher.update(str(transaction).encode())
        return hasher.hexdigest()

class StorageEngine:
    def store_block(self, block):
        # Placeholder implementation, store block data in database
        # Use block['block_hash'] to identify the block in the database
        pass

    def fetch_block(self, block_hash):
        # Placeholder implementation, retrieve block data from database
        return {}

    def fetch_transaction(self, transaction_hash):
        # Placeholder implementation, retrieve transaction data from database
        return {}

    def fetch_balance(self, account_address):
        # Placeholder implementation, retrieve account balance from database
        return {}

# Create instances of components
validation_engine = ValidationEngine()
mempool = Mempool()
storage_engine = StorageEngine()
miner = Miner(mempool, storage_engine)

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

@app.route('/get_transaction/<transaction_hash>', methods=['GET'])
def get_transaction(transaction_hash):
    transaction_data = storage_engine.fetch_transaction(transaction_hash)
    return jsonify(transaction_data)

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

    try:
        while True:
            time.sleep(1)  # Keep the main thread running
    except KeyboardInterrupt:
        miner.running = False
        miner.join()  # Wait for the miner thread to finish
        flask_thread.join()  # Wait for the Flask thread to finish
