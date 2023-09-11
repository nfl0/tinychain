from aiohttp import web
import asyncio
import logging
import ecdsa
from ecdsa import VerifyingKey
import plyvel
import json
import blake3
import websockets

from block import Block
from parameters import BLOCK_REWARD, BLOCK_TIME, MAX_TX_BLOCK, MAX_TX_POOL, VALIDATOR_PUBLIC_KEY
PORT = 5001
PEER_ADDR = 'http://127.0.0.1:5000/ws'

# Create a dictionary to store WebSocket connections.
websocket_connections = {}

app = web.Application()

class Transaction:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.message = f"{self.sender}-{self.receiver}-{self.amount}"
        self.transaction_hash = self.generate_transaction_hash()
        self.memo = kwargs.get('memo', '')
        self.confirmed = None

    def generate_transaction_hash(self):
        values = [str(self.sender), str(self.receiver), str(self.amount), str(self.signature)]
        return blake3.blake3(''.join(values).encode()).hexdigest()

    def to_dict(self):
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'signature': self.signature,
            'memo': self.memo,
            'confirmed': self.confirmed
        }

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
        # Check the block's transactions
        for transaction in block.transactions:
            if not self.validate_transaction(transaction):
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

            # Filter out already confirmed transactions
            transactions_to_include = [t for t in valid_transactions_to_forge if t.confirmed is None][:MAX_TX_BLOCK]

            block = Block(self.block_height, transactions_to_include, self.validator_address, self.previous_block_hash)

            if self.validation_engine.validate_block(block):
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

            self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data).encode())
            
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


# syncing

async def handle_ws_connection(websocket, path):
    try:
        if path == '/ws':
            await handle_peer_connection(websocket)
        elif path == '/local_ws':
            await handle_local_connection(websocket)
        else:
            await websocket.close()
    except Exception as e:
        logging.error(f"WebSocket error: {e}")

async def handle_peer_connection(websocket):
    global websocket_connections
    try:
        peer_address = await websocket.recv()
        websocket_connections[peer_address] = websocket
        await sync_transaction_pool(websocket)
        await sync_blocks(websocket)
    except Exception as e:
        logging.error(f"Peer WebSocket error: {e}")
    finally:
        await websocket.close()
        if peer_address in websocket_connections:
            del websocket_connections[peer_address]

async def handle_local_connection(websocket):
    try:
        while True:
            data = await websocket.recv()
            message = json.loads(data)
            if message['type'] == 'transaction':
                await handle_local_transaction(message['transaction'])
            elif message['type'] == 'block':
                await handle_local_block(message['block'])
    except Exception as e:
        logging.error(f"Local WebSocket error: {e}")
    finally:
        await websocket.close()

async def handle_local_transaction(transaction_data):
    # Handle incoming transactions from local node
    transaction = Transaction(**transaction_data)
    if validation_engine.validate_transaction(transaction):
        transactionpool.add_transaction(transaction)
        await sync_transaction_pool_to_peers(transaction)

async def handle_local_block(block_data):
    # Handle incoming blocks from local node
    block = Block(**block_data)
    if validation_engine.validate_block(block):
        storage_engine.store_block(block)
        await sync_blocks_to_peers(block)

async def sync_transaction_pool(websocket):
    # Synchronize the transaction pool with a new peer
    transactions = transactionpool.get_transactions()
    transaction_data = [transaction.to_dict() for transaction in transactions]
    await websocket.send(json.dumps({'type': 'transaction_pool', 'data': transaction_data}))

async def sync_transaction_pool_to_peers(transaction):
    # Broadcast a new transaction to all connected peers
    for peer_address, peer_websocket in websocket_connections.items():
        try:
            await peer_websocket.send(json.dumps({'type': 'transaction', 'transaction': transaction.to_dict()}))
        except Exception as e:
            logging.error(f"Failed to send transaction to {peer_address}: {e}")

async def sync_blocks(websocket):
    # Synchronize blocks with a new peer
    last_block = storage_engine.fetch_last_block()
    await websocket.send(json.dumps({'type': 'blocks', 'last_block': last_block}))

async def sync_blocks_to_peers(block):
    # Broadcast a new block to all connected peers
    for peer_address, peer_websocket in websocket_connections.items():
        try:
            await peer_websocket.send(json.dumps({'type': 'block', 'block': block.to_dict()}))
        except Exception as e:
            logging.error(f"Failed to send block to {peer_address}: {e}")

# end syncing

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine()
storage_engine.open_databases()
validation_engine = ValidationEngine(storage_engine)
transactionpool = TransactionPool(max_size=MAX_TX_POOL)
last_block_data = storage_engine.fetch_last_block()
validator = Forger(transactionpool, storage_engine, validation_engine, VALIDATOR_PUBLIC_KEY, last_block_data)

# API endpoints
async def send_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        required_fields = ['sender', 'receiver', 'amount', 'signature']
        if all(field in transaction_data for field in required_fields):
            transaction = Transaction(**transaction_data)
            if validation_engine.validate_transaction(transaction):
                transactionpool.add_transaction(transaction)
                return web.json_response({'message': 'Transaction added to the transaction pool', 'transaction_hash': transaction.transaction_hash})
    
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

    # Create WebSocket server
    start_server = websockets.serve(handle_ws_connection, '0.0.0.0', PORT)

    loop.run_until_complete(start_server)
    loop.create_task(validator.forge_new_block())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(start_server.ws_server.close())  # Replace 'site' with 'start_server.ws_server.close()'
        loop.run_until_complete(app_runner.cleanup())
