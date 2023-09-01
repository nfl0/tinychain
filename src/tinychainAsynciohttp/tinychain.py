from aiohttp import web
import asyncio
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


app = web.Application()

BLOCK_TIME = 5
BLOCK_REWARD = 10
VALIDATOR_PUBLIC_KEY = 'aa9cbc6fe2966cd9343aab811e38cdfea9364c6563bf4939015f700d15c629a381af89af25ea29beb073c695f155f6d22abd1c864f8339e7f3536e88c2c6b98c'

transaction_schema = {
    "type": "object",
    "properties": {
        "sender": {"type": "string"},
        "receiver": {"type": "string"},
        "amount": {"type": "number"},
        "signature": {"type": "string"},
        "memo": {"type": "string"}
    },
    "required": ["sender", "receiver", "amount", "signature"]
}

class Transaction:
    def __init__(self, sender, receiver, amount, signature, memo=None):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.signature = signature
        self.memo = memo
        self.message = f"{sender}-{receiver}-{amount}"
        self.transaction_hash = self.generate_transaction_hash()

    def generate_transaction_hash(self):
        values = [str(self.sender), str(self.receiver), str(self.amount), str(self.signature)]
        return blake3.blake3(''.join(values).encode()).hexdigest()

class TransactionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Transaction):
            return vars(obj)
        return super().default(obj)

class Block:
    def __init__(self, height, transactions, validator_address, previous_block_hash=None):
        self.height = height
        self.transactions = transactions
        self.timestamp = int(time.time())
        self.validator = validator_address
        self.previous_block_hash = previous_block_hash
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        sorted_transaction_hashes = [t.transaction_hash for t in sorted(self.transactions, key=lambda t: t.transaction_hash)]
        values = sorted_transaction_hashes + [str(self.timestamp)]
        if self.previous_block_hash:
            values.append(str(self.previous_block_hash))
        return blake3.blake3(''.join(values).encode()).hexdigest()


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
    def __init__(self, max_size):
        self.transactions = {}
        self.max_size = max_size

    def add_transaction(self, transaction):
        if len(self.transactions) < self.max_size:
            sender = transaction.sender
            self.transactions[sender] = transaction

    def remove_transaction(self, transaction):
        sender = transaction.sender
        if sender in self.transactions:
            del self.transactions[sender]

    def get_transactions(self):
        return list(self.transactions.values())

    def is_empty(self):
        return len(self.transactions) == 0

class Forger:
    def __init__(self, mempool, storage_engine, validation_engine, validator_address, last_block_data):
        self.mempool = mempool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.validator_address = validator_address
        self.running = True
        self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
        self.block_height = last_block_data['height'] + 1 if last_block_data else 0
        self.block_timer = None

    async def forge_new_block(self):
        while self.running:
            transactions_to_forge = self.mempool.get_transactions()
            valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)]

            transactions_to_include = valid_transactions_to_forge[:3]

            block = Block(self.block_height, transactions_to_include, self.validator_address, self.previous_block_hash)
            self.storage_engine.store_block(block)

            for transaction in transactions_to_include:
                self.mempool.remove_transaction(transaction)

            self.previous_block_hash = block.block_hash
            self.block_height += 1

            await asyncio.sleep(BLOCK_TIME)

    def start(self):
        asyncio.create_task(self.forge_new_block())

    def stop(self):
        self.running = False

class StorageEngine:
    def __init__(self):
        self.db_blocks = None
        self.db_accounts = None
        self.last_block_hash = None

    def open_databases(self):
        try:
            self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
            self.db_accounts = plyvel.DB('accounts.db', create_if_missing=True)
        except Exception as e:
            logging.error(f"Failed to open databases: {e}")

    def close_databases(self):
        try:
            if self.db_blocks:
                self.db_blocks.close()
            if self.db_accounts:
                self.db_accounts.close()
        except Exception as e:
            logging.error(f"Failed to close databases: {e}")

    def store_block(self, block):
        try:
            block_data = {
                'height': block.height,
                'transactions': block.transactions,
                'timestamp': block.timestamp,
                'validator': block.validator,
                'block_hash': block.block_hash,
                'previous_block_hash': block.previous_block_hash
            }
            self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data, cls=TransactionEncoder).encode())
            
            # Update validator account balance with block reward
            validator_balance = self.fetch_balance(block.validator)
            if validator_balance is None:
                self.db_accounts.put(block.validator.encode(), str(0).encode())
            if validator_balance is not None:
                self.db_accounts.put(block.validator.encode(), str(validator_balance + BLOCK_REWARD).encode())

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
        except Exception as e:
            logging.error(f"Failed to store block: {e}")

    def fetch_balance(self, account_address):
        try:
            balance = self.db_accounts.get(account_address.encode())
            if balance is not None:
                return int(balance.decode())
        except Exception as e:
            logging.error(f"Failed to fetch balance: {e}")
        return None

    def fetch_block(self, block_hash):
        try:
            block_data = self.db_blocks.get(block_hash.encode())
            if block_data is not None:
                return json.loads(block_data.decode())
        except Exception as e:
            logging.error(f"Failed to fetch block: {e}")
        return None
    
    def fetch_last_block(self):
        last_block = None
        try:
            for block_hash, block_data in self.db_blocks.iterator(reverse=True):
                block_info = json.loads(block_data.decode())
                if last_block is None or block_info['height'] > last_block['height']:
                    last_block = block_info
        except Exception as e:
            logging.error(f"Failed to fetch last block: {e}")
        return last_block
    
    def close(self):
        self.close_databases()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
storage_engine.open_databases()
validation_engine = ValidationEngine(storage_engine)
mempool = Mempool(max_size=1000)
last_block_data = storage_engine.fetch_last_block()
validator = Forger(mempool, storage_engine, validation_engine, VALIDATOR_PUBLIC_KEY, last_block_data)

# API endpoints
async def send_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(
                sender=transaction_data['sender'],
                receiver=transaction_data['receiver'],
                amount=int(transaction_data['amount']),
                signature=transaction_data['signature'],
                memo=transaction_data.get('memo')
            )
            if validation_engine.validate_transaction(transaction):
                mempool.add_transaction(transaction)
                return web.json_response({'message': 'Transaction added to mempool', 'transaction_hash': transaction.transaction_hash})
        except jsonschema.exceptions.ValidationError:
            pass
    return web.json_response({'error': 'Invalid transaction data'}, status=400)

async def get_block_by_hash(request):
    block_hash = request.match_info['block_hash']
    block_data = storage_engine.fetch_block(block_hash)
    if block_data is not None:
        return web.json_response(block_data)
    return web.json_response({'error': 'Block not found'}, status=404)

async def get_balance(request):
    account_address = request.match_info['account_address']
    balance = storage_engine.fetch_balance(account_address)
    if balance is not None:
        return web.json_response({'balance': balance})
    return web.json_response({'error': 'Account not found'}, status=404)

app.router.add_post('/send_transaction', send_transaction)
app.router.add_get('/get_block/{block_hash}', get_block_by_hash)
app.router.add_get('/get_balance/{account_address}', get_balance)

async def cleanup(app):
    validator.stop()
    await asyncio.gather(*[t for t in asyncio.all_tasks() if t is not asyncio.current_task()])
    storage_engine.close()

app.on_cleanup.append(cleanup)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    app_runner = web.AppRunner(app)
    loop.run_until_complete(app_runner.setup())
    
    site = web.TCPSite(app_runner, host='0.0.0.0', port=5000)
    loop.run_until_complete(site.start())

    loop.create_task(validator.forge_new_block()) 
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(site.stop())
        loop.run_until_complete(app_runner.cleanup())
