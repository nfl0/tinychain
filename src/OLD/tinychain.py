from flask import Flask, request, jsonify
import threading
import time
import blake3
import logging
import ecdsa
from ecdsa import VerifyingKey
import atexit
import plyvel
import json
from jsonschema import validate
import jsonschema

app = Flask(__name__)

BLOCK_TIME = 5
BLOCK_REWARD = 10
miner_public_key = 'aa9cbc6fe2966cd9343aab811e38cdfea9364c6563bf4939015f700d15c629a381af89af25ea29beb073c695f155f6d22abd1c864f8339e7f3536e88c2c6b98c'

# Define JSON schema for transaction data validation
transaction_schema = {
    "type": "object",
    "properties": {
        "sender": {"type": "string"},
        "receiver": {"type": "string"},
        "amount": {"type": "number"},
        "signature": {"type": "string"}
    },
    "required": ["sender", "receiver", "amount", "signature"]
}

class Transaction:
    def __init__(self, sender, receiver, amount, signature):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.signature = signature
        self.message = f"{sender}-{receiver}-{amount}"
        self.transaction_hash = self.generate_transaction_hash()

    def generate_transaction_hash(self):
        hasher = blake3.blake3()
        hasher.update(str(self.sender).encode())
        hasher.update(str(self.receiver).encode())
        hasher.update(str(self.amount).encode())
        hasher.update(str(self.signature).encode())
        return hasher.hexdigest()

class TransactionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Transaction):
            return {
                'hash': obj.transaction_hash,
                'sender': obj.sender,
                'receiver': obj.receiver,
                'amount': obj.amount,
                'signature': obj.signature
            }
        return super().default(obj)

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
        sorted_transactions = sorted(self.transactions, key=lambda t: t.transaction_hash)
        for transaction in sorted_transactions:
            hasher.update(transaction.transaction_hash.encode())
        hasher.update(str(self.timestamp).encode())
        if self.previous_block_hash:
            hasher.update(str(self.previous_block_hash).encode())
        return hasher.hexdigest()

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def validate_transaction(self, transaction):
        if isinstance(transaction, Transaction):
            sender_balance = self.storage_engine.fetch_balance(transaction.sender)
            if sender_balance is not None and sender_balance >= transaction.amount:
                if self.verify_transaction_signature(transaction):
                    return True
        return False

    def verify_transaction_signature(self, transaction):
        public_key = transaction.sender
        signature = transaction.signature
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=ecdsa.SECP256k1)
        try:
            vk.verify(bytes.fromhex(signature), transaction.message.encode())
            return True
        except ecdsa.BadSignatureError:
            return False

class Mempool:
    def __init__(self):
        self.transactions = {}

    def add_transaction(self, transaction):
        sender = transaction.sender
        if sender in self.transactions:
            self.transactions[sender] = transaction
        else:
            self.transactions[sender] = transaction

    def remove_transaction(self, transaction):
        sender = transaction.sender
        if sender in self.transactions:
            del self.transactions[sender]

    def get_transactions(self):
        return list(self.transactions.values())

    def is_empty(self):
        return len(self.transactions) == 0


class Miner(threading.Thread):
    def __init__(self, mempool, storage_engine, validation_engine, miner_address, last_block_data):
        super().__init__()
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.miner_address = miner_address
        self.running = True
        self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
        self.block_height = last_block_data['height'] + 1 if last_block_data else 0
        self.block_timer = None

    def mine_block(self):
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

        self.block_timer = threading.Timer(BLOCK_TIME, self.mine_block)
        self.block_timer.start()

    def run(self):
        self.block_timer = threading.Timer(0, self.mine_block)
        self.block_timer.start()

    def stop(self):
        self.block_timer.cancel()
        self.running = False

class StorageEngine:
    def __init__(self):
        self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
        self.db_accounts = plyvel.DB('accounts.db', create_if_missing=True)
        self.last_block_hash = None

    def store_block(self, block):
        block_data = {
            'height': block.height,
            'transactions': block.transactions,
            'timestamp': block.timestamp,
            'miner': block.miner,
            'block_hash': block.block_hash,
            'previous_block_hash': block.previous_block_hash
        }
        self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data, cls=TransactionEncoder).encode())
        
        # Update miner account balance with block reward
        miner_balance = self.fetch_balance(block.miner)
        if miner_balance is None:
            self.db_accounts.put(block.miner.encode(), str(0).encode())
        if miner_balance is not None:
            self.db_accounts.put(block.miner.encode(), str(miner_balance + BLOCK_REWARD).encode())

        # Update account balances for transactions
        for transaction in block.transactions:
            sender = transaction.sender
            receiver = transaction.receiver
            amount = transaction.amount
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
validation_engine = ValidationEngine(storage_engine)
mempool = Mempool()
last_block_data = storage_engine.fetch_last_block()
miner = Miner(mempool, storage_engine, validation_engine, miner_public_key, last_block_data)

# API endpoints
@app.route('/send_transaction', methods=['POST'])
def send_transaction():
    data = request.json
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(
                sender=transaction_data['sender'],
                receiver=transaction_data['receiver'],
                amount=int(transaction_data['amount']),
                signature=transaction_data['signature']
            )
            if validation_engine.validate_transaction(transaction):
                mempool.add_transaction(transaction)
                return jsonify({'message': 'Transaction added to mempool', 'transaction_hash': transaction.transaction_hash})
        except jsonschema.exceptions.ValidationError:
            pass
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
