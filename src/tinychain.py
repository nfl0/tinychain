from flask import Flask, request, jsonify
import threading
import time
import random
import blake3  # Ensure you have installed blake3-py using 'pip install blake3'

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, utils

app = Flask(__name__)

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def validate_transaction(self, transaction):
        sender_address = transaction.get('sender')
        receiver_address = transaction.get('receiver')
        amount = transaction.get('amount')
        signature = transaction.get('signature')

        if not all([sender_address, receiver_address, amount, signature]):
            return 'incomplete_data'  # Transaction data is incomplete

        sender_public_key = self.storage_engine.fetch_public_key(sender_address)
        if not sender_public_key:
            return 'sender_key_not_found'  # Sender's public key not found

        sender_balance = self.storage_engine.fetch_balance(sender_address)
        if sender_balance is None or sender_balance < amount + 1:
            return 'insufficient_balance'  # Insufficient balance

        # Verify the cryptographic signature
        try:
            public_key = serialization.load_pem_public_key(sender_public_key.encode())
            public_key.verify(
                signature,
                transaction.get('data').encode(),
                padding.PSS(mgf=padding.MGF1(utils.Prehashed(utils.PrehashedSHA256())), salt_length=padding.PSS.MAX_LENGTH),
                utils.Prehashed(utils.PrehashedSHA256())
            )
        except Exception as e:
            print(f"Signature verification error: {e}")
            return 'signature_verification_failed'  # Signature verification failed

        return True

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
    def __init__(self):
        self.blocks_db = {}
        self.accounts_db = {}

    def store_block(self, block):
        block_hash = block['block_hash']
        self.blocks_db[block_hash] = block

    def fetch_block(self, block_hash):
        return self.blocks_db.get(block_hash)

    def store_transaction(self, transaction_hash, transaction):
        self.accounts_db.setdefault(transaction['sender'], {'balance': 0})
        self.accounts_db.setdefault(transaction['receiver'], {'balance': 0})

        sender_balance = self.accounts_db[transaction['sender']]['balance']
        receiver_balance = self.accounts_db[transaction['receiver']]['balance']
        
        sender_balance -= transaction['amount'] + 1
        receiver_balance += transaction['amount']

        self.accounts_db[transaction['sender']]['balance'] = sender_balance
        self.accounts_db[transaction['receiver']]['balance'] = receiver_balance

    def fetch_balance(self, account_address):
        account_data = self.accounts_db.get(account_address)
        if account_data:
            return account_data['balance']
        return None

    def store_public_key(self, account_address, public_key):
        self.accounts_db.setdefault(account_address, {})
        self.accounts_db[account_address]['public_key'] = public_key

    def fetch_public_key(self, account_address):
        account_data = self.accounts_db.get(account_address)
        if account_data:
            return account_data.get('public_key')
        return None


# Create instances of components
storage_engine = StorageEngine()
validation_engine = ValidationEngine(storage_engine)
mempool = Mempool()

miner = Miner(mempool, storage_engine)

# Define API endpoints
@app.route('/send_transaction', methods=['POST'])
def send_transaction():
    data = request.json
    if 'transaction' in data:
        transaction = data['transaction']
        validation_result = validation_engine.validate_transaction(transaction)
        if validation_result is True:
            mempool.add_transaction(transaction)
            return jsonify({'message': 'Transaction added to mempool'})
        else:
            error_message = 'Invalid transaction'
            if validation_result == 'incomplete_data':
                error_message = 'Transaction data is incomplete'
            elif validation_result == 'insufficient_balance':
                error_message = 'Insufficient balance'
            elif validation_result == 'sender_key_not_found':
                error_message = "Sender's public key not found"
            elif validation_result == 'signature_verification_failed':
                error_message = 'Signature verification failed'

            return jsonify({'error': error_message})
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
