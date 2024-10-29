from aiohttp import web
import asyncio
import logging
import plyvel
import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import blake3
import time
from block import BlockHeader, Block, Signature
from transaction import Transaction, transaction_schema
from validation_engine import ValidationEngine
from vm import TinyVMEngine
from wallet import Wallet
from parameters import HTTP_PORT, MAX_TX_POOL, PEER_URIS # todo: implement MAX_TX_BLOCK

TINYCOIN = 1000000000000000000
TINYCHAIN_UNIT = 'tatoshi'


PEER_URIS = '127.0.0.1:5010'

app = web.Application()
    
class TransactionPool:
    def __init__(self, max_size):
        self.transactions = {}
        self.max_size = max_size
    def add_transaction(self, transaction):
        if len(self.transactions) >= self.max_size:
            raise ValueError("Transaction pool is full")
        if len(self.transactions) < self.max_size:
            self.transactions[transaction.transaction_hash] = transaction
    def remove_transaction(self, transaction):
        self.transactions.pop(transaction.transaction_hash, None)
    def get_transactions(self):
        return sorted(self.transactions.values(), key=lambda tx: tx.fee, reverse=True)
    def get_transaction_by_hash(self, hash):
        return self.transactions[hash]
    def is_empty(self):
        return not self.transactions


class Forger:
    def __init__(self, transactionpool, storage_engine, validation_engine, wallet):
        self.transactionpool = transactionpool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine

        self.wallet = wallet
        self.validator = self.proposer = self.wallet.get_address()
        self.sign = self.wallet.sign_message

        self.production_enabled = True

        self.in_memory_blocks = {}  # P7e15
        self.in_memory_block_headers = {}  # P7e15

        self.current_proposer_index = 0  # Initialize the current proposer index

    @staticmethod
    def generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash):
        values = [merkle_root, str(timestamp), str(state_root), previous_block_hash]
        concatenated_string = f"{''.join(values)}".encode()
        return blake3.blake3(concatenated_string).hexdigest()

    @staticmethod
    def compute_merkle_root(transaction_hashes):
        if len(transaction_hashes) == 0:
            return blake3.blake3(b'').hexdigest()

        while len(transaction_hashes) > 1:
            if len(transaction_hashes) % 2 != 0:
                transaction_hashes.append(transaction_hashes[-1])

            if isinstance(transaction_hashes[0], bytes):
                transaction_hashes = [blake3.blake3(transaction_hashes[i] + transaction_hashes[i + 1]).digest() for i in range(0, len(transaction_hashes), 2)]
            elif isinstance(transaction_hashes[0], str):
                transaction_hashes = [blake3.blake3(transaction_hashes[i].encode() + transaction_hashes[i + 1].encode()).digest() for i in range(0, len(transaction_hashes), 2)]
            else:
                raise TypeError("Unsupported data type in transaction_hashes")
            
        if isinstance(transaction_hashes[0], str):
            # If it's a string, encode it as bytes using UTF-8
            transaction_hashes[0] = transaction_hashes[0].encode('utf-8')

        return blake3.blake3(transaction_hashes[0]).hexdigest()
    
    def toggle_production(self):
        self.production_enabled = not self.production_enabled

    def fetch_current_validator_set(self):
        staking_contract_state = self.storage_engine.fetch_contract_state("7374616b696e67")
        if staking_contract_state:
            return sorted(staking_contract_state.keys(), key=lambda k: staking_contract_state[k]['index'])
        return []

    def select_proposer(self):
        validator_set = self.fetch_current_validator_set()
        if validator_set:
            proposer = validator_set[self.current_proposer_index]
            self.current_proposer_index = (self.current_proposer_index + 1) % len(validator_set)
            return proposer
        return None

    def forge_new_block(self, replay=True, block_header=None, is_genesis=False):
        if not self.production_enabled:
            return "Forging is disabled"

        transactions_to_forge = []

        if replay is True:
            for transaction_hash in block_header.transaction_hashes:
                # Get the transaction from the transaction pool by its hash
                transaction = self.transactionpool.get_transaction_by_hash(transaction_hash)
                if transaction is not None:
                    # Append the transaction to the transactions_to_forge array
                    transactions_to_forge.append(transaction)
                else:
                    logging.info(f"Transaction {transaction_hash} not found in pool, requesting transaction from peers...")
                    # todo: request transaction from connected peers (or the block producer?)
        else:
            transactions_to_forge = self.transactionpool.get_transactions()

        if is_genesis is False:
            valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)]
        else:
            valid_transactions_to_forge = transactions_to_forge

        # Get the previous block for validation
        if is_genesis is False:
            previous_block_header = self.storage_engine.fetch_last_block_header()
            previous_block_hash = previous_block_header.block_hash
            height = previous_block_header.height + 1
            current_state = self.storage_engine.fetch_state(previous_block_header.state_root)
        else:
            height = 0
            current_state = {}
        
        tvm_engine = TinyVMEngine(current_state)

        if replay is False:
            if is_genesis is False:
                ### NEW BLOCK PROPOSAL CASE ###
                # set proposer address
                self.proposer = self.wallet.get_address()
                # generate timestamp
                timestamp = int(time.time())
                # generate state root
                state_root, new_state = tvm_engine.exec(valid_transactions_to_forge, self.proposer)
                # generate merkle root
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in valid_transactions_to_forge]
                merkle_root = self.compute_merkle_root(transaction_hashes)
                # generate block hash
                block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash)
                # sign the block
                signature = self.sign(block_hash)
                validator_index = self.get_validator_index(self.proposer)
                signatures = [Signature(self.proposer, timestamp, signature, validator_index)]
            else:
                ### GENESIS BLOCK CASE ###
                self.proposer = "genesis"
                timestamp = int(19191919)
                # generate state root
                state_root, new_state = tvm_engine.exec(transactions_to_forge, self.proposer)
                # generate merkle root
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in transactions_to_forge]
                merkle_root = self.compute_merkle_root(transaction_hashes)
                # generate block hash
                previous_block_hash = "00000000"
                block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash)
                # genesis signature
                signature = "genesis_signature"
                validator_index = -1
                signatures = [Signature(self.proposer, timestamp, signature, validator_index)]

            block_header = BlockHeader(
                block_hash,
                height,
                timestamp,
                previous_block_hash,
                merkle_root,
                state_root,
                self.proposer,
                signatures,
                transaction_hashes
            )
        else:
            ### BLOCK REPLAY CASE ###
            # execute transactions
            state_root, new_state = tvm_engine.exec(valid_transactions_to_forge, block_header.proposer)
            # check if state_root matches
            if state_root == block_header.state_root:
                # check if merkle_root matches
                # todo: check the merkle root first (cheaper)
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in block_header.transactions]
                computed_merkle_root = self.compute_merkle_root(transaction_hashes)
                if computed_merkle_root == block_header.merkle_root:
                    signature = self.wallet.sign_message(block_hash)
                    validator_index = self.get_validator_index(self.validator)
                    signatures = block_header.signatures
                    logging.info("Block signatures: %s", signatures)

                    if isinstance(signatures, list) and all(isinstance(sig, Signature) for sig in signatures):
                        signatures.append(Signature(self.validator, int(time.time()), signature, validator_index))
                    else:
                        signatures = [Signature.from_dict(sig) for sig in signatures]
                        signatures.append(Signature(self.validator, int(time.time()), signature, validator_index))

                    block_header = BlockHeader(
                        block_header.block_hash,
                        block_header.height,
                        block_header.timestamp,
                        block_header.previous_block_hash,
                        block_header.merkle_root,
                        block_header.state_root,
                        block_header.proposer,
                        signatures,
                        block_header.transaction_hashes
                    )
                    logging.info("Replay successful for block %s", block_header.block_hash)
                else:
                    logging.error("Replay failed for block %s (Merkle root mismatch)", block_header.block_hash)
                    return False
            else:
                logging.error("Replay failed for block %s (State root mismatch)", block_header.block_hash)
                return False
        
        # todo: validate block_header?
        if is_genesis is False:
            block = Block(block_header, valid_transactions_to_forge)
        else:
            block = Block(block_header, transactions_to_forge)

        if is_genesis is False:
            self.in_memory_blocks[block.header.block_hash] = block  # P9ad7
            self.in_memory_block_headers[block.header.block_hash] = block_header  # P9ad7

            # Broadcast block header to validators and collect signatures (P02ef)
            self.broadcast_block_header(block_header)

            # Check if 2/3 validators have signed
            if self.has_enough_signatures(block_header):

                # Store the finalized block
                self.storage_engine.store_block(block)

                self.storage_engine.store_block_header(block_header)
                self.storage_engine.store_state(block.header.state_root, new_state)
                return True
            else:
                # Drop the block if not enough signatures
                del self.in_memory_blocks[block.header.block_hash]
                del self.in_memory_block_headers[block.header.block_hash]
                return False
        else:
            self.storage_engine.store_block(block)
            self.storage_engine.store_block_header(block_header)
            self.storage_engine.store_state(block.header.state_root, new_state)
            return True

    async def broadcast_block_header(self, block_header):  # P02ef
        for peer_uri in PEER_URIS:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f'http://{peer_uri}/receive_block', json={'block_header': block_header.to_dict()}) as response:
                        if response.status == 200:
                            logging.info(f"Block header broadcasted to peer {peer_uri}")
                        else:
                            logging.error(f"Failed to broadcast block header to peer {peer_uri}")
            except Exception as e:
                logging.error(f"Error broadcasting block header to peer {peer_uri}: {e}")

    def has_enough_signatures(self, block_header):  # P66ad
        # Logic to check if 2/3 validators have signed
        return True

    def get_validator_index(self, validator_address):
        staking_contract_state = self.storage_engine.fetch_contract_state("7374616b696e67")
        if staking_contract_state and validator_address in staking_contract_state:
            return staking_contract_state[validator_address]['index']
        return -1

def genesis_procedure():
    genesis_addresses = [
        "7ff08d4ddd1be1305e77db4064bb71f2c0872599334db03fc36d8cab3fb349c4e1dfb6262bd3e118f37aa8d19827f0aa56bf9052bb9c5b6e16e0679706124e38",
        "336bf5193983cb2c287f7695343730ccf5f0a88da961459e996b1d4cc07480f1649a682e1194db36bd9957e6cb6cfb4c2185306f31da9723bc84b03e4116ce57",
        "448769135d4bef3c2b88f81829dc73433fd05882082bb67c4962ba9ef2acf6967083d7f142758150f6f01a87e7a18aa568400b5a05b2b24ccce415d764fed636",
        "f0689410ce583320822fb2761600b1786860711ec751fae27d2341ea1befbcc0a3c1afde193e9d2d5d9a9f5a79c7f18efa49e4f5905767c4d518b9c78850305f",
        "ce8958afa7c8ac763308705cda306d21119f5401d08d249b1cdcbd6306faba91c6f31a210c7827a494891d17d357dfa755a6e4ae5dd09ffa3803fbafe58c027c",
        "de280016480735a12e975d4c869808bdee564d544e762020446462261d704d8d4a8cab311c6447e3299108b7317db9d5316057c0c0cf7379dda2cd12c20d7660"
    ]
    staking_contract_address = "7374616b696e67"  # the word 'staking' in hex
    # genesis transactions
    genesis_transactions = [
        Transaction("genesis", genesis_addresses[0], 1000*TINYCOIN, 120, 0, "consensus", ""),
        Transaction(genesis_addresses[0], staking_contract_address, 500*TINYCOIN, 110, 0, "genesis_signature_0", "stake"),
        Transaction("genesis", genesis_addresses[1], 1000*TINYCOIN, 100, 1, "consensus", ""),
        Transaction(genesis_addresses[1], staking_contract_address, 500*TINYCOIN, 90, 0, "genesis_signature_1", "stake"),
        Transaction("genesis", genesis_addresses[2], 1000*TINYCOIN, 80, 2, "consensus", ""),
        Transaction(genesis_addresses[2], staking_contract_address, 500*TINYCOIN, 70, 0, "genesis_signature_2", "stake"),
        Transaction("genesis", genesis_addresses[3], 1000*TINYCOIN, 60, 3, "consensus", ""),
        Transaction(genesis_addresses[3], staking_contract_address, 500*TINYCOIN, 50, 0, "genesis_signature_3", "stake"),
        Transaction("genesis", genesis_addresses[4], 1000*TINYCOIN, 40, 4, "consensus", ""),
        Transaction(genesis_addresses[4], staking_contract_address, 500*TINYCOIN, 30, 0, "genesis_signature_4", "stake"),
        Transaction("genesis", genesis_addresses[5], 1000*TINYCOIN, 20, 5, "consensus", ""),
        Transaction(genesis_addresses[5], staking_contract_address, 500*TINYCOIN, 10, 0, "genesis_signature_5", "stake")
    ]
    # loop through the genesis transactions and add to transaction pool
    for transaction in genesis_transactions:
        transactionpool.add_transaction(transaction)
    
    # call the forge_new_block method
    forger.forge_new_block(False, None, True)
    
class StorageEngine:
    def __init__(self, transactionpool):
        self.transactionpool = transactionpool
        self.db_headers = None
        self.db_blocks = None
        self.db_transactions = None
        self.db_states = None
        self.state = []
        
    def open_databases(self):
        try:
            self.db_headers = plyvel.DB('headers.db', create_if_missing=True)
            self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
            self.db_transactions = plyvel.DB('transactions.db', create_if_missing=True)
            self.db_states = plyvel.DB('states.db', create_if_missing=True)
            # if the headers database is empty, call genesis_procedure()
            headers = self.db_headers.iterator()
            if not any(headers):
                genesis_procedure()
            else:
                logging.info("Databases already initialized")

        except Exception as err:
            logging.error("Failed to open databases: %s", err)
            raise
            
    def close_databases(self):
        try:
            if self.db_headers:
                self.db_headers.close()
            if self.db_blocks:
                self.db_blocks.close()
            if self.db_transactions:
                self.db_transactions.close()
            if self.db_states:
                self.db_states.close()
        except Exception as err:
            logging.error("Failed to close databases: %s", err)
            raise

    def store_block(self, block):
        try:
            if block.header.state_root is None:
                logging.error("Block storage skipped: 'NoneType' object has no attribute 'state_root'")
                return
            
            for transaction in block.transactions:
                transaction.confirmed = block.header.height
                self.store_transaction(transaction)
                self.transactionpool.remove_transaction(transaction)
                self.set_nonce_for_account(transaction.sender, transaction.nonce + 1)

            block_data = {
                'block_hash': block.header.block_hash,
                'height': block.header.height,
                'timestamp': block.header.timestamp,
                'merkle_root': block.header.merkle_root,
                'state_root': block.header.state_root,
                'previous_block_hash': block.header.previous_block_hash,
                'proposer': block.header.proposer,
                'signatures': [sig.to_dict() for sig in block.header.signatures],
                'transactions': [transaction.to_dict() for transaction in block.transactions]
            }

            self.db_blocks.put(block.header.block_hash.encode(), json.dumps(block_data).encode())

            logging.info("Stored block: %s at height %s", block.header.block_hash, block.header.height)
        except Exception as err:
            logging.error("Failed to store block: %s", err)

    def store_block_header(self, block_header):
        try:
            block_header_data = {
                'block_hash': block_header.block_hash,
                'height': block_header.height,
                'timestamp': block_header.timestamp,
                'merkle_root': block_header.merkle_root,
                'state_root': block_header.state_root,
                'previous_block_hash': block_header.previous_block_hash,
                'proposer': block_header.proposer,
                'signatures': [sig.to_dict() for sig in block_header.signatures],
                'transaction_hashes': block_header.transaction_hashes # revisit this line
            }

            self.db_headers.put(str(block_header.height).encode(), json.dumps(block_header_data).encode())

            logging.info("Stored block header: %s at height %s", block_header.block_hash, block_header.height)
        except Exception as err:
            logging.error("Failed to store block header: %s", err)

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
                "memo": transaction.memo,
                "confirmed": transaction.confirmed
            }
            self.db_transactions.put(transaction.transaction_hash.encode(), json.dumps(transaction_data).encode('utf-8'))
            logging.info("Stored transaction: %s", transaction.transaction_hash)
        except Exception as err:
            logging.error("Failed to store transaction: %s", err)

    def store_state(self, state_root, state):
        try:
            self.db_states.put(state_root.encode(), json.dumps(state).encode())
            logging.info("State saved: %s", state_root) # saved for when voting period ends and > 2/3 validators have signed
        except Exception as err:
            logging.error("Failed to store state: %s", err)        

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
                if isinstance(account_data, dict):
                    balance = account_data.get("balance", 0)
                    nonce = account_data.get("nonce", 0)
                    return balance, nonce
                else:
                    return account_data, 0
        return 0, 0
    
    def set_nonce_for_account(self, account_address, nonce):
        contract_address = "6163636f756e7473"
        accounts_state = self.fetch_contract_state(contract_address)
        if accounts_state is not None:
            if account_address in accounts_state:
                accounts_state[account_address]["nonce"] = nonce
            else:
                accounts_state[account_address] = {"balance": 0, "nonce": nonce}
            self.store_contract_state(contract_address, accounts_state)

    def store_contract_state(self, contract_address, state_data):
        try:
            self.db_states.put(contract_address.encode(), json.dumps(state_data).encode())
            logging.info("Stored contract state for address: %s", contract_address)
        except Exception as err:
            logging.error("Failed to store contract state: %s", err)

    def fetch_state(self, state_root):
        state_data = self.db_states.get(state_root.encode())
        return json.loads(state_data.decode()) if state_data is not None else None

    def fetch_contract_state(self, contract_address):
        state_root = self.fetch_last_block_header().state_root  #state root is None at genesis block
        contract_state_data = self.db_states.get(state_root.encode()) # Pdb0d
        return json.loads(contract_state_data.decode()).get(contract_address) if contract_state_data is not None else None # Pc603
    
    def close(self):
        self.close_databases()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
wallet = Wallet()
if not wallet.is_initialized():
    print("Wallet is not initialized. Please run wallet_generator.py to generate a wallet.")
    exit()
transactionpool = TransactionPool(max_size=MAX_TX_POOL)
storage_engine = StorageEngine(transactionpool)
validation_engine = ValidationEngine(storage_engine)
forger = Forger(transactionpool, storage_engine, validation_engine, wallet)


async def broadcast_transaction(transaction, sender_uri):
    for peer_uri in PEER_URIS:
        if peer_uri != sender_uri:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f'http://{peer_uri}/send_transaction', json={'transaction': transaction.to_dict()}) as response:
                        if response.status == 200:
                            logging.info(f"Transaction broadcasted to peer {peer_uri}")
                        else:
                            logging.error(f"Failed to broadcast transaction to peer {peer_uri}")
            except Exception as e:
                logging.error(f"Error broadcasting transaction to peer {peer_uri}: {e}")

async def send_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(**transaction_data)
            if validation_engine.validate_transaction(transaction):
                if transaction.transaction_hash not in transactionpool.transactions:
                    transactionpool.add_transaction(transaction)
                    sender_uri = request.remote
                    await broadcast_transaction(transaction, sender_uri)
                    return web.json_response({'message': 'Transaction added to the transaction pool', 'transaction_hash': transaction.transaction_hash})
        except ValidationError:
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

async def toggle_production(request):
    forger.toggle_production()
    production_status = "enabled" if forger.production_enabled else "disabled"
    return web.json_response({'message': f'Block production {production_status}'})

async def get_nonce(request):
    account_address = request.match_info['account_address']
    nonce = storage_engine.get_nonce_for_account(account_address)
    return web.json_response({'nonce': nonce})

def find_proposer_signature(block_header):
    for signature in block_header.signatures:
        if signature.validator_address == block_header.proposer:
            return signature
    return None

async def receive_block_header(request):
    data = await request.json()
    block_header_data = data.get('block_header')
    if not block_header_data:
        return web.json_response({'error': 'Invalid block header data'}, status=400)

    block_header = BlockHeader.from_dict(block_header_data)

    # Verify the validity of the block header
    if not validation_engine.validate_block_header(block_header, storage_engine.fetch_last_block_header()):
        return web.json_response({'error': 'Invalid block header'}, status=400)

    # Verify the identity of the proposer through the included signature
    proposer_signature = find_proposer_signature(block_header)
    if proposer_signature is None or not Wallet.verify_signature(block_header.block_hash, proposer_signature.signature_data, proposer_signature.validator_address):
        return web.json_response({'error': 'Invalid proposer signature'}, status=400)

    # Check if a block header with the same hash already exists in memory
    if block_header.block_hash in forger.in_memory_block_headers:
        existing_block_header = forger.in_memory_block_headers[block_header.block_hash]
        existing_block_header.append_signatures(block_header.signatures)
    else:
        # Submit the received block header to the forger for replay
        forger.forge_new_block(replay=True, block_header=block_header)

    return web.json_response({'message': 'Block header received and processed'})

app.router.add_post('/toggle_production', toggle_production)
app.router.add_post('/send_transaction', send_transaction)
app.router.add_get('/get_block/{block_hash}', get_block_by_hash)
app.router.add_get('/transactions/{transaction_hash}', get_transaction_by_hash)
app.router.add_get('/get_nonce/{account_address}', get_nonce)

app.router.add_post('/receive_block', receive_block_header)

async def cleanup(app):
    await asyncio.gather(*[t for t in asyncio.all_tasks() if t is not asyncio.current_task()])
    storage_engine.close()

app.on_cleanup.append(cleanup)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    app_runner = web.AppRunner(app)
    loop.run_until_complete(app_runner.setup())
    
    site = web.TCPSite(app_runner, host='0.0.0.0', port=HTTP_PORT)
    loop.run_until_complete(site.start())

    storage_engine.open_databases()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(site.stop())
        loop.run_until_complete(app_runner.cleanup())
