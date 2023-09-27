from aiohttp import web
import aiohttp
import asyncio
import logging
import plyvel
import json
from jsonschema import validate
import jsonschema
import blake3
import time

from block import BlockHeader, Block
from block import block_schema
from transaction import transaction_schema
from validation_engine import ValidationEngine
from vm import TinyVMEngine
from wallet import Wallet
from parameters import HTTP_PORT, BLOCK_TIME, MAX_TX_BLOCK, MAX_TX_POOL, VALIDATOR_PUBLIC_KEY

# 1 tinycoin = 1000000000000000000 tatoshi
# tinychain node only understands tatoshi
tinycoin = 1000000000000000000


PEER_URIS = '127.0.0.1:5010'

app = web.Application()

class Transaction:
    def __init__(self, fee, nonce, **kwargs):
        self.__dict__.update(kwargs)
        self.memo = kwargs.get('memo', '')
        self.message = f"{self.sender}-{self.receiver}-{self.amount}-{self.memo}"
        self.transaction_hash = self.generate_transaction_hash()
        self.confirmed = None
        self.fee = fee
        self.nonce = nonce

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
    def __init__(self, transactionpool, storage_engine, validation_engine, wallet, validator_address):
        self.transactionpool = transactionpool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.wallet = wallet
        self.validator_address = validator_address
        self.running = True
        self.production_enabled = True

    def toggle_production(self):
        self.production_enabled = not self.production_enabled

    @staticmethod
    def generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash):
        values = [merkle_root, str(timestamp), str(state_root), previous_block_hash]
        concatenated_string = ''.join(values).encode()
        return blake3.blake3(concatenated_string).hexdigest()

    @staticmethod
    def compute_merkle_root(transaction_hashes):
        if len(transaction_hashes) == 0:
            return blake3.blake3(b'').hexdigest()

        while len(transaction_hashes) > 1:
            if len(transaction_hashes) % 2 != 0:
                transaction_hashes.append(transaction_hashes[-1])
            transaction_hashes = [blake3.blake3(transaction_hashes[i].encode() + transaction_hashes[i + 1].encode()).digest() for i in range(0, len(transaction_hashes), 2)]

        if isinstance(transaction_hashes[0], str):
            # If it's a string, encode it as bytes using UTF-8
            transaction_hashes[0] = transaction_hashes[0].encode('utf-8')

        return blake3.blake3(transaction_hashes[0]).hexdigest()
    
    async def forge_new_block(self, replay=True, block_header=None):
        while self.running:
            if not self.production_enabled:
                await asyncio.sleep(BLOCK_TIME)
                continue
            if replay is False:
                transactions_to_forge = self.transactionpool.get_transactions()
            else:
                transactions_to_forge = block_header.transactions

            valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)] # todo: check if transaction.nonce = previous nonce + 1

            # Get the previous block for validation
            previous_block_header = self.storage_engine.fetch_last_block_header()
            previous_block_hash = previous_block_header.block_hash
            block_height = previous_block_header.height + 1

            if replay is False:
                validator = self.wallet.get_address()
                timestamp = int(time.time())
                # generate state root
                state_root = self.tvm_engine.exec(valid_transactions_to_forge, validator)
                # generate merkle root
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in valid_transactions_to_forge]
                merkle_root = self.compute_merkle_root(transaction_hashes)
                # generate block hash
                block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash)
                # sign the block
                signature = [self.wallet.sign_message(block_hash)]

                block_header = BlockHeader(
                    block_height,
                    timestamp,
                    previous_block_hash,
                    state_root,
                    validator,
                    signature,
                    transaction_hashes
                )

            block = Block(block_header, valid_transactions_to_forge)

            if self.validation_engine.validate_block(block, previous_block_header):
                # keep in memory while 2/3 validators sign?
                self.storage_engine.store_block(block)

            await asyncio.sleep(BLOCK_TIME)

    def start(self):
        asyncio.create_task(self.forge_new_block())

    def stop(self):
        self.running = False

class StorageEngine:
    def __init__(self, transactionpool):
        self.transactionpool = transactionpool
        self.db_headers = None
        self.db_blocks = None
        self.db_transactions = None
        self.db_states = None
        self.open_databases()
        self.create_genesis_block()

    def get_genesis_transactions(self):
        return [Transaction(sender="000000000000000000000000000000000000000000000000000000000000000", receiver=VALIDATOR_PUBLIC_KEY, amount=100000000000, signature="0000000000000000000000000000000000000000000000000000000000", memo="genesis")]

    def create_genesis_block(self):
        if self.fetch_last_block_header() is None:
            # todo: try to sync from peers
            genesis_block = Block(0, [], VALIDATOR_PUBLIC_KEY, "0000000000000000000000000000000000000000000000000000000000000000", 1465154705)
            self.store_block(genesis_block, is_sync=True, is_genesis=True)

    def open_databases(self):
        try:
            self.db_headers = plyvel.DB('headers.db', create_if_missing=True)
            self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
            self.db_transactions = plyvel.DB('transactions.db', create_if_missing=True)
            self.db_states = plyvel.DB('state.db', create_if_missing=True)
        except Exception as e:
            logging.error(f"Failed to open databases: {e}")

    def close_databases(self):
        try:
            self.db_headers.close()
            self.db_blocks.close()
            self.db_transactions.close()
            self.db_states.close()
        except Exception as e:
            logging.error(f"Failed to close databases: {e}")

    def set_tvm_engine(self, tvm_engine):
        self.tvm_engine = tvm_engine

    def store_block(self, block, is_sync=False, is_genesis=False):
        if hasattr(self, 'tvm_engine') and self.tvm_engine.execute_block(block) is False:
            logging.info("Block failed to execute")
            return
        else:
            logging.info("Block executed")

        try:
            block_data = {
                'block_hash': block.block_hash,
                'height': block.height,
                'timestamp': block.timestamp,
                'merkle_root': block.merkle_root,
                'state_root': block.state_root,
                'previous_block_hash': block.previous_block_hash,
                'validator': block.validator,
                'signature': block.signature,
                'transactions': [transaction.to_dict() for transaction in block.transactions]
            }

            if not is_genesis:
                # broadcast_block(block)
                print(block_data)
            else:
                print("genesis block")
                print(block_data)

            # Loop through transactions and update their confirmed attribute
            for transaction in block.transactions:
                transaction.confirmed = block.height

            # db_blocks should store the block data which is the block header and block body
            # Store the block to the database
            self.db_blocks.put(block.block_hash.encode(), json.dumps(block_data).encode())


            for transaction in block.transactions:
                self.transactionpool.remove_transaction(transaction)
                self.set_nonce_for_account(transaction.sender, transaction.nonce + 1)

            logging.info(f"Stored block: {block.block_hash} at height {block.height}")
        except Exception as e:
            logging.error(f"Failed to store block: {e}")


    def store_transaction(self, transaction):
        try:
            transaction_data = {
                'transaction_hash': transaction.transaction_hash,
                "sender": transaction.sender,
                "receiver": transaction.receiver,
                "amount": transaction.amount,
                "fee": transaction.fee,
                "nonce": transaction.nonce,
                "signature": transaction.signature,
                "memo": transaction.memo
            }
            self.db_transactions.put(transaction.transaction_hash.encode(), json.dumps(transaction_data))
            logging.info(f"Stored transaction: {transaction.transaction_hash}")
        except Exception as e:
            logging.error(f"Failed to store transaction: {e}")

    def fetch_balance(self, account_address):
        accounts_state = self.fetch_contract_state("6163636f756e7473")
        if accounts_state is not None:
            return accounts_state.get(account_address, None)
        return None

    def fetch_block(self, block_hash):
        block_data = self.db_blocks.get(block_hash.encode())
        return json.loads(block_data.decode()) if block_data is not None else None
    
    def fetch_last_block_header(self):
        last_block_header = None
        max_height = -1
        
        if self.db_headers is not None:
            for header_key, header_data in self.db_headers.iterator(reverse=True):
                block_header = BlockHeader.from_dict(json.loads(header_data.decode()))
                if block_header.height > max_height:
                    max_height = block_header.height
                    last_block_header = block_header

        return last_block_header

    def fetch_transaction(self, transaction_hash):
        transaction_data = self.db_transactions.get(transaction_hash.encode())
        return json.loads(transaction_data.decode()) if transaction_data is not None else None

    def get_nonce_for_account(self, account_address):
        accounts_state = self.fetch_contract_state("6163636f756e7473")
        if accounts_state is not None:
            account_data = accounts_state.get(account_address, None)
            if account_data is not None:
                balance, nonce = account_data
                return nonce
        return 0
    
    def set_nonce_for_account(self, account_address, nonce):
        contract_address = "6163636f756e7473"
        accounts_state = self.fetch_contract_state(contract_address)
        if accounts_state is not None:
            if account_address in accounts_state:
                accounts_state[account_address][1] = nonce
            else:
                accounts_state[account_address] = [0, nonce]
            self.store_contract_state(contract_address, accounts_state)

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
wallet = Wallet()
transactionpool = TransactionPool(max_size=MAX_TX_POOL)
storage_engine = StorageEngine(transactionpool)
validation_engine = ValidationEngine(storage_engine)
forger = Forger(transactionpool, storage_engine, validation_engine, wallet, VALIDATOR_PUBLIC_KEY)
tvm_engine = TinyVMEngine(storage_engine)
storage_engine.set_tvm_engine(tvm_engine)


# Api Endpoints

'''
async def broadcast_block(block):
    try:
        block_data = block.to_dict()  # Serialize the block to a dictionary
        for peer_uri in PEER_URIS:
            async with aiohttp.ClientSession() as session:
                url = f"http://{peer_uri}/receive_block"
                async with session.post(url, json=block_data) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        logging.info(f"Block sent to {peer_uri}: {response_data}")
                    else:
                        logging.info(f"Failed to send block to {peer_uri}")
    except aiohttp.ClientError as e:
        logging.info(f"Error sending block to peers: {e}")

async def receive_block(request):
    try:
        block_data = await request.json()
        # Deserialize the received block data into a Block object
        received_block = Block.from_dict(block_data)

        # Validate the received block before adding it to the blockchain
        if isinstance(received_block, Block) is False:
            return web.json_response({'error': 'Invalid block data'}, status=400)
        if Wallet.verify_signature(received_block.validator, received_block.block_hash, received_block.signature) is False:
            return web.json_response({'error': 'Invalid block data'}, status=400)
        if validation_engine.validate_block(received_block, storage_engine.fetch_last_block_header()):
            storage_engine.store_block(received_block, is_sync=True)
            return web.json_response({'message': 'Block added to the blockchain', 'block_hash': received_block.block_hash})
        else:
            return web.json_response({'error': 'Invalid block data'}, status=400)
    except json.JSONDecodeError:
        return web.json_response({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return web.json_response({'error': f'Error receiving block: {str(e)}'}, status=500)
'''
'''
async def broadcast_transaction(transaction_data):
    for peer_uri in PEER_URIS:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{peer_uri}/receive_transaction"
                async with session.post(url, json={'transaction': transaction_data}) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        logging.info(f"Transaction sent to {peer_uri}: {response_data}")
                    else:
                        logging.info(f"Failed to send transaction to {peer_uri}")
        except aiohttp.ClientError as e:
            logging.info(f"Error sending transaction to {peer_uri}: {e}")
'''
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

async def get_transaction_by_hash(request):
    transaction_hash = request.match_info['transaction_hash']
    transaction_data = storage_engine.fetch_transaction(transaction_hash)
    if transaction_data is not None:
        return web.json_response(transaction_data)
    return web.json_response({'error': 'Block not found'}, status=404)

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
    forger.toggle_production()
    production_status = "enabled" if forger.production_enabled else "disabled"
    return web.json_response({'message': f'Block production {production_status}'})

app.router.add_post('/toggle_production', toggle_production)
app.router.add_post('/send_transaction', send_transaction)
app.router.add_post('/receive_transaction', receive_transaction)
app.router.add_get('/get_block/{block_hash}', get_block_by_hash)
app.router.add_get('/transactions/{transaction_hash}', get_transaction_by_hash)
app.router.add_get('/get_balance/{account_address}', get_balance)
#app.router.add_post('/receive_block', receive_block)

async def cleanup(app):
    forger.stop()
    await asyncio.gather(*[t for t in asyncio.all_tasks() if t is not asyncio.current_task()])
    storage_engine.close()

app.on_cleanup.append(cleanup)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    app_runner = web.AppRunner(app)
    loop.run_until_complete(app_runner.setup())
    
    site = web.TCPSite(app_runner, host='0.0.0.0', port=HTTP_PORT)
    loop.run_until_complete(site.start())

    loop.create_task(forger.forge_new_block()) 
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(site.stop())
        loop.run_until_complete(app_runner.cleanup())
