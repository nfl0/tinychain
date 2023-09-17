from aiohttp import web
import aiohttp
import asyncio
import logging
import plyvel
import json
from jsonschema import validate
import jsonschema
import blake3

from block import Block
from transaction import transaction_schema
from validation_engine import ValidationEngine
from vm import TinyVMEngine
from parameters import HTTP_PORT, BLOCK_TIME, MAX_TX_BLOCK, MAX_TX_POOL, VALIDATOR_PUBLIC_KEY

PEER_URIS = ['localhost:5010', 'localhost:5020']

app = web.Application()

class Transaction:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.memo = kwargs.get('memo', '')
        self.message = f"{self.sender}-{self.receiver}-{self.amount}-{self.memo}"
        self.transaction_hash = self.generate_transaction_hash()
        self.confirmed = None

    def generate_transaction_hash(self):
        values = [str(self.sender), str(self.receiver), str(self.amount), str(self.signature)]
        return blake3.blake3(''.join(values).encode()).hexdigest()

    def to_dict(self):
        return {
            'transaction_hash': self.transaction_hash,
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'signature': self.signature,
            'memo': self.memo,
            'confirmed': self.confirmed
        }

class TransactionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Transaction):
            return obj.to_dict()
        return super().default(obj)
    
class TransactionPool:
    def __init__(self, max_size):
        self.transactions = {}
        self.max_size = max_size
    def add_transaction(self, transaction):
        if len(self.transactions) < self.max_size:
            self.transactions[transaction.sender] = transaction
    def remove_transaction(self, transaction):
        self.transactions.pop(transaction.sender, None)
    def get_transactions(self):
        return list(self.transactions.values())
    def is_empty(self):
        return not self.transactions

class Forger:
    def __init__(self, transactionpool, storage_engine, validation_engine, validator_address, last_block_data):
        self.transactionpool = transactionpool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.validator_address = validator_address
        self.running = True
        self.production_enabled = True
        self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
        self.block_height = (last_block_data['height'] + 1) if last_block_data else 0
        self.block_timer = None

    def toggle_production(self):
        self.production_enabled = not self.production_enabled

    async def forge_new_block(self):
        while self.running:
            if not self.production_enabled:
                await asyncio.sleep(BLOCK_TIME)
                continue

            transactions_to_forge = self.transactionpool.get_transactions()

            valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)]

            # Filter out already confirmed transactions
            transactions_to_include = [t for t in valid_transactions_to_forge if t.confirmed is None][:MAX_TX_BLOCK]

            # Get the previous block for validation
            previous_block_data = storage_engine.fetch_last_block()
            previous_block = Block.from_dict(previous_block_data) if previous_block_data else None

            # Create a new block
            block = Block(self.block_height, transactions_to_include, self.validator_address, self.previous_block_hash)

            if self.validation_engine.validate_block(block, previous_block):
                for transaction in transactions_to_include:
                    transaction.confirmed = self.block_height

                self.storage_engine.store_block(block)

                for transaction in transactions_to_include:
                    self.transactionpool.remove_transaction(transaction)

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
        self.db_states = None
        self.last_block_hash = None

    def open_databases(self):
        try:
            self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
            self.db_states = plyvel.DB('tvm_states.db', create_if_missing=True)
        except Exception as e:
            logging.error(f"Failed to open databases: {e}")

    def close_databases(self):
        try:
            self.db_blocks.close()
            self.db_states.close()
        except Exception as e:
            logging.error(f"Failed to close databases: {e}")

    def store_block(self, block):
        try:
            block_data = {
            'height': block.height,
            'transactions': [transaction.to_dict() for transaction in block.transactions],
            'timestamp': block.timestamp,
            'validator': block.validator,
            'merkle_root': block.merkle_root,
            'block_hash': block.block_hash,
            'previous_block_hash': block.previous_block_hash
            }

            self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data, cls=TransactionEncoder).encode())
            
            tvm_engine.execute_block(block)

            self.last_block_hash = block.block_hash

            logging.info(f"Stored block: {block.block_hash}")
        except Exception as e:
            logging.error(f"Failed to store block: {e}")

    def fetch_balance(self, account_address):
        accounts_state = self.fetch_contract_state("6163636f756e7473")
        if accounts_state is not None:
            return accounts_state.get(account_address, None)
        return None

    def fetch_block(self, block_hash):
        block_data = self.db_blocks.get(block_hash.encode())
        return json.loads(block_data.decode()) if block_data is not None else None
    
    def fetch_last_block(self):
        last_block = None
        for block_hash, block_data in self.db_blocks.iterator(reverse=True):
            block_info = json.loads(block_data.decode())
            if last_block is None or block_info['height'] > last_block['height']:
                last_block = block_info
        return last_block
    
    def store_contract_state(self, contract_address, state_data):
        try:
            self.db_states.put(contract_address.encode(), json.dumps(state_data).encode())
            logging.info(f"Stored contract state for address: {contract_address}")
        except Exception as e:
            logging.error(f"Failed to store contract state: {e}")

    def fetch_contract_state(self, contract_address):
        state_data = self.db_states.get(contract_address.encode())
        return json.loads(state_data.decode()) if state_data is not None else None
    
    def close(self):
        self.close_databases()


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
storage_engine.open_databases()
validation_engine = ValidationEngine(storage_engine)
transactionpool = TransactionPool(max_size=MAX_TX_POOL)
last_block_data = storage_engine.fetch_last_block()
validator = Forger(transactionpool, storage_engine, validation_engine, VALIDATOR_PUBLIC_KEY, last_block_data)
tvm_engine = TinyVMEngine(storage_engine)

# Function to send transactions to all connected peers
async def broadcast_transaction(transaction_data):
    for peer_uri in PEER_URIS:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{peer_uri}/receive_transaction"
                async with session.post(url, json={'transaction': transaction_data}) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        print(f"Transaction sent to {peer_uri}: {response_data}")
                    else:
                        print(f"Failed to send transaction to {peer_uri}")
        except aiohttp.ClientError as e:
            print(f"Error sending transaction to {peer_uri}: {e}")

# API endpoints
async def send_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(**transaction_data)
            if validation_engine.validate_transaction(transaction):
                transactionpool.add_transaction(transaction)
                await broadcast_transaction(transaction_data)
                return web.json_response({'message': 'Transaction added to the transaction pool', 'transaction_hash': transaction.transaction_hash})
        except jsonschema.exceptions.ValidationError:
            pass
    return web.json_response({'error': 'Invalid transaction data'}, status=400)

# Endpoint to receive transactions from other peers
async def receive_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(**transaction_data)
            if validation_engine.validate_transaction(transaction):
                transactionpool.add_transaction(transaction)
                logging.info("[Receiver API] transaction received")
                return web.json_response({'message': 'Transaction added to the transaction pool', 'transaction_hash': transaction.transaction_hash})
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

async def toggle_production(request):
    validator.toggle_production()
    production_status = "enabled" if validator.production_enabled else "disabled"
    return web.json_response({'message': f'Block production {production_status}'})

app.router.add_post('/toggle_production', toggle_production)
app.router.add_post('/send_transaction', send_transaction)
app.router.add_post('/receive_transaction', receive_transaction)
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
    
    site = web.TCPSite(app_runner, host='0.0.0.0', port=HTTP_PORT)
    loop.run_until_complete(site.start())

    loop.create_task(validator.forge_new_block()) 
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(site.stop())
        loop.run_until_complete(app_runner.cleanup())