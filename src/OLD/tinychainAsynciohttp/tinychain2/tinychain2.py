from aiohttp import web
import asyncio
import logging
import ecdsa
from ecdsa import VerifyingKey
import plyvel
import json
from jsonschema import validate
import jsonschema
import aiohttp
from jsonrpcserver import method, async_dispatch as dispatch

from transaction import Transaction
from block import Block
from parameters import BLOCK_REWARD, BLOCK_TIME, MAX_TX_BLOCK, VALIDATOR_PUBLIC_KEY, PEER_ADDR, POOL_MAX_TX, PORT

app = web.Application()

transaction_schema = {
    "type": "object",
    "properties": {
        "sender": {"type": "string"},
        "receiver": {"type": "string"},
        "amount": {"type": "number"},
        "signature": {"type": "string"},
        "memo": {"type": "string"},
        "confirmed": {"type": "integer"}  # Include the 'confirmed' field
    },
    "required": ["sender", "receiver", "amount", "signature"]
}

class TransactionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Transaction):
            return obj.to_dict()
        return super().default(obj)

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def validate_transaction(self, transaction):
        sender_balance = self.storage_engine.fetch_balance(transaction.sender)
        if sender_balance is not None and sender_balance >= transaction.amount and self.verify_transaction_signature(transaction):
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

    def validate_block(self, block):
        # Check the block's structure and fields
        if not isinstance(block, Block):
            return False

        # Check the block's timestamp, maybe add a validation rule here
        # if block.timestamp > current_timestamp:
        #     return False

        # Check the block's transactions
        for transaction in block.transactions:
            if not self.validate_transaction(transaction):
                return False

        # Check the previous block hash
        last_block_data = self.storage_engine.fetch_last_block()
        if last_block_data and block.previous_block_hash != last_block_data['block_hash']:
            return False

        return True

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
        self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
        self.block_height = (last_block_data['height'] + 1) if last_block_data else 0
        self.block_timer = None

    async def forge_new_block(self):
        while self.running:
            transactions_to_forge = self.transactionpool.get_transactions()
            valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)]

            transactions_to_include = [t for t in valid_transactions_to_forge if t.confirmed is None][:MAX_TX_BLOCK]

            block = Block(self.block_height, transactions_to_include, self.validator_address, self.previous_block_hash)

            if self.validation_engine.validate_block(block):
                for transaction in transactions_to_include:
                    transaction.confirmed = self.block_height

                self.storage_engine.store_block(block)

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
            self.db_blocks.close()
            self.db_accounts.close()
        except Exception as e:
            logging.error(f"Failed to close databases: {e}")

    def store_block(self, block):
        try:
            block_data = {
                'height': block.height,
                'transactions': [transaction.to_dict() for transaction in block.transactions],
                'timestamp': block.timestamp,
                'validator': block.validator,
                'block_hash': block.block_hash,
                'previous_block_hash': block.previous_block_hash
            }

            self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data, cls=TransactionEncoder).encode())

            # Update validator account balance with block reward
            validator_balance = self.fetch_balance(block.validator)
            if validator_balance is None:
                validator_balance = 0
            new_balance = validator_balance + BLOCK_REWARD
            self.db_accounts.put(block.validator.encode(), str(new_balance).encode())

            # Update account balances for transactions
            for transaction in block.transactions:
                sender, receiver, amount = transaction.sender, transaction.receiver, transaction.amount
                sender_balance, receiver_balance = self.fetch_balance(sender), self.fetch_balance(receiver)
                if sender_balance is not None:
                    self.db_accounts.put(sender.encode(), str(sender_balance - amount).encode())
                if receiver_balance is None:
                    receiver_balance = 0
                self.db_accounts.put(receiver.encode(), str(receiver_balance + amount).encode())

            self.last_block_hash = block.block_hash

            logging.info(f"Stored block: {block.block_hash}")
        except Exception as e:
            logging.error(f"Failed to store block: {e}")

    def fetch_balance(self, account_address):
        balance = self.db_accounts.get(account_address.encode())
        return int(balance.decode()) if balance is not None else None

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

    def close(self):
        self.close_databases()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
storage_engine.open_databases()
validation_engine = ValidationEngine(storage_engine)
transactionpool = TransactionPool(max_size=POOL_MAX_TX)
last_block_data = storage_engine.fetch_last_block()
validator = Forger(transactionpool, storage_engine, validation_engine, VALIDATOR_PUBLIC_KEY, last_block_data)

# JSON-RPC Methods

@method
async def get_transaction_pool():
    return transactionpool.get_transactions()

@method
async def update_transaction_pool(transactions):
    try:
        # Assuming that 'transactions' is a list of transaction dictionaries
        for tx_data in transactions:
            try:
                validate(instance=tx_data, schema=transaction_schema)
                transaction = Transaction(**tx_data)
                if validation_engine.validate_transaction(transaction):
                    transactionpool.add_transaction(transaction)
                else:
                    print(f"Transaction validation failed: {transaction}")
            except jsonschema.exceptions.ValidationError as e:
                print(f"Validation error: {e}")
        return True
    except Exception as e:
        print(f"Error in update_transaction_pool: {e}")
        return False


async def broadcast_transaction(transaction_data):
    # Assuming PEER_ADDR is a list of URLs of other nodes
    for peer_url in PEER_ADDR:
        try:
            async with aiohttp.ClientSession() as session:
                request_data = {
                    "jsonrpc": "2.0",
                    "method": "update_transaction_pool",
                    "params": [transaction_data],
                    "id": 1,
                }
                async with session.post(peer_url, json=request_data) as response:
                    if response.status == 200:
                        try:
                            response_data = await response.json()
                            print(f"Response from peer {peer_url}: {response_data}")
                            if "error" in response_data:
                                print(f"Error from peer {peer_url}: {response_data['error']}")
                        except Exception as e:
                            print(f"Error parsing response from peer {peer_url}: {str(e)}")
                    else:
                        print(f"HTTP error from peer {peer_url}: {response.status}")
        except Exception as e:
            print(f"Error while broadcasting transaction to {peer_url}: {str(e)}")


# API endpoints
async def send_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(**transaction_data)
            if validation_engine.validate_transaction(transaction):
                # Broadcast the transaction to other nodes
                await broadcast_transaction(transaction.to_dict())
                transactionpool.add_transaction(transaction)
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

app.router.add_post('/send_transaction', send_transaction)
app.router.add_get('/get_block/{block_hash}', get_block_by_hash)
app.router.add_get('/get_balance/{account_address}', get_balance)

# JSON-RPC endpoint
async def handle_rpc(request):
    response = await dispatch(await request.text())
    return web.json_response(response)

app.router.add_post('/rpc', handle_rpc)

async def cleanup(app):
    validator.stop()
    await asyncio.gather(*[t for t in asyncio.all_tasks() if t is not asyncio.current_task()])
    storage_engine.close()

app.on_cleanup.append(cleanup)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    app_runner = web.AppRunner(app)
    loop.run_until_complete(app_runner.setup())

    site = web.TCPSite(app_runner, host='0.0.0.0', port=PORT)
    loop.run_until_complete(site.start())

    loop.create_task(validator.forge_new_block())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(site.stop())
        loop.run_until_complete(app_runner.cleanup())
