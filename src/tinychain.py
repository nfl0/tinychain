from aiohttp import web
import asyncio
import logging
import plyvel
import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import blake3
import time
from block import BlockHeader, Block
from transaction import Transaction, transaction_schema
from validation_engine import ValidationEngine
from vm import TinyVMEngine
from wallet import Wallet
from parameters import HTTP_PORT, MAX_TX_POOL # todo: implement MAX_TX_BLOCK

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
        return sorted(list(self.transactions.values()), key=lambda tx: tx.fee, reverse=True)
    def get_transaction_by_hash(self, hash):
        return self.transactions[hash]
    def is_empty(self):
        return not self.transactions


class Forger:
    def __init__(self, transactionpool, storage_engine, validation_engine, tvm_engine, wallet):
        self.transactionpool = transactionpool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine
        self.tvm_engine = tvm_engine
        self.wallet = wallet
        self.validator = self.wallet.get_address()
        self.production_enabled = True

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
            transaction_hashes = [blake3.blake3(transaction_hashes[i].encode() + transaction_hashes[i + 1].encode()).digest() for i in range(0, len(transaction_hashes), 2)]

        if isinstance(transaction_hashes[0], str):
            # If it's a string, encode it as bytes using UTF-8
            transaction_hashes[0] = transaction_hashes[0].encode('utf-8')

        return blake3.blake3(transaction_hashes[0]).hexdigest()
    
    def toggle_production(self):
        self.production_enabled = not self.production_enabled

    def forge_new_block(self, replay=True, block_header=None, is_genesis=False):
        if not self.production_enabled:
            return "Forging is disabled"

        transactions_to_forge = []
        if is_genesis is True:
            transactions_to_forge = self.transactionpool.get_transactions()
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

        valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)]  # todo: check if transaction.nonce = previous nonce + 1. update! a new nonce calculation maybe needed

        # Get the previous block for validation
        if is_genesis is False:
            previous_block_header = self.storage_engine.fetch_last_block_header()
            previous_block_hash = previous_block_header.block_hash
            height = previous_block_header.height + 1
        else:
            height = 0

        if replay is False:
            if is_genesis is False:
                timestamp = int(time.time())
                # generate state root
                state_root, new_state= self.tvm_engine.exec(valid_transactions_to_forge, self.validator)
                # generate merkle root
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in valid_transactions_to_forge]
                merkle_root = self.compute_merkle_root(transaction_hashes)
                # generate block hash
                block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash)
                # sign the block
                signature = self.wallet.sign_message(block_hash)
                signatures = [{self.validator, signature}]
            else:
                timestamp = int(19191919)
                # generate state root
                state_root, new_state= self.tvm_engine.exec(transactions_to_forge, "genesis")
                # generate merkle root
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in valid_transactions_to_forge]
                merkle_root = self.compute_merkle_root(transaction_hashes)
                # generate block hash
                previous_block_hash = "00000000"
                block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash)
                # genesis signature
                signatures = []
                signature = "genesis_signature"

                self.validator = "genesis"

            block_header = BlockHeader(
                block_hash,
                height,
                timestamp,
                previous_block_hash,
                merkle_root,
                state_root,
                self.validator,
                signatures.append({self.validator, signature}),
                transaction_hashes
            )
            logging.info(block_header.transaction_hashes)
        else:
            # execute transactions
            state_root, new_state = self.tvm_engine.exec(valid_transactions_to_forge, block_header.validator)
            # check if state_root matches
            if state_root == block_header.state_root:
                # check if merkle_root matches
                # todo: check the merkle root first (cheaper)
                transaction_hashes = [t.to_dict()['transaction_hash'] for t in block_header.transactions]
                computed_merkle_root = self.compute_merkle_root(transaction_hashes)
                if computed_merkle_root == block_header.merkle_root:
                    signature = self.wallet.sign_message(block_hash)
                    signatures = block_header.signatures
                    logging.info("Block signatures: %s", signatures)

                    block_header = BlockHeader(
                        block_header.block_hash,
                        block_header.height,
                        block_header.timestamp,
                        block_header.previous_block_hash,
                        block_header.merkle_root,
                        block_header.state_root,
                        block_header.validator,
                        signatures.append({self.validator, signature}),
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

        block = Block(block_header, valid_transactions_to_forge)

        if is_genesis is False:
            if self.validation_engine.validate_block(block, previous_block_header):
                #self.storage_engine.store_block(block) # todo: change to, keep the block header in memory until 2/3 validators sign. elif consensus fail, drop?
                #self.storage_engine.store_block_header(block_header)
                #self.storage_engine.store_state({block.header.state_root: new_state})
                return block, new_state
        else:
            self.storage_engine.store_block(block) # todo: change to, keep the block header in memory until 2/3 validators sign. elif consensus fail, drop?
            self.storage_engine.store_block_header(block_header)
            self.storage_engine.store_state({block.header.state_root: new_state})

            #logging.info("Block forged and stored: %s at height %s", block_header.block_hash, block_header.height)

        logging.info("Block forging failed")
        return False

def genesis_procedure():
    genesis_addresses = [
        "374225f9043c475981d2da0fd3efbe6b8e382bb3802c062eacfabe5e0867052238ed6acaf99c5c33c1cce1a3e1ef757efd9c857417f26e2e1b5d9ab9e90c9b4d",
        "50c43f64ba255a95ab641978af7009eecef03610d120eb35035fdb0ea3c1b7f05859382f117ff396230b7cb453992d3b0da1c03f8a0572086eb938862bf6d77e",
    ]
    staking_contract_address = "7374616b696e67"  # the word 'staking' in hex
    # genesis transactions
    genesis_transactions = [
        Transaction("genesis", genesis_addresses[0], 1000*TINYCOIN, 1, 0, "consensus", ""),
        Transaction(genesis_addresses[0], staking_contract_address, 500*TINYCOIN, 2, 0, "genesis_signature_0", "stake"),
        Transaction("genesis", genesis_addresses[1], 1000*TINYCOIN, 3, 1, "consensus", ""),
        Transaction(genesis_addresses[1], staking_contract_address, 500*TINYCOIN, 4, 0, "genesis_signature_1", "stake")
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
        #self.open_databases()
        self.state = None

    # todo: implement the genesis block logic along the DBs initialization, in seperate genesis.py
    # if the dbs are not initialized, the program should exist and inform the user to first run the genesis.py to initialize the databases
    # every time the program starts, it should first try to connect to peers and sync the blockchain. only then, the node can participate (or request to participate) in consensus/block production
    # reminder: the node won't be allowed to participate in consensus if it's stake is 0

    # ABOVE NOTES PROBABLY DEPRECATED!

    # Genesis Procedure:
    # if databases are empty: seed the transactionpool with the genesis block transactions: ("genesis", genesis_addresses[n], amount: 500, transfer), and (genesis_addresses[n], staking_contract_address, amount: 500, stake)
    # then call forge_new_block (is_genesis=True) to forge the genesis block
    
    # todo: implement the block_header storage logic and figure the key is height or block_hash
    
        
    def open_databases(self):
        try:
            self.db_headers = plyvel.DB('headers.db', create_if_missing=True)
            self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
            self.db_transactions = plyvel.DB('transactions.db', create_if_missing=True)
            self.db_states = plyvel.DB('state.db', create_if_missing=True)
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
            block_data = {
                'block_hash': block.header.block_hash,
                'height': block.header.height,
                'timestamp': block.header.timestamp,
                'merkle_root': block.header.merkle_root,
                'state_root': block.header.state_root,
                'previous_block_hash': block.header.previous_block_hash,
                'validator': block.header.validator,
                'signatures': block.header.signatures,
                'transactions': [transaction.to_dict() for transaction in block.transactions]
            }

            for transaction in block.transactions:
                transaction.confirmed = block.height
                self.store_transaction(transaction)
                self.transactionpool.remove_transaction(transaction)
                self.set_nonce_for_account(transaction.sender, transaction.nonce + 1)

            self.db_blocks.put(block.header.height.encode(), json.dumps(block_data).encode())

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
                'validator': block_header.validator,
                'signatures': block_header.signatures,
                'transaction_hashes': block_header.transaction_hashes # reviset this line
            }

            self.db_headers.put(block_header.height.encode(), json.dumps(block_header_data).encode())

            logging.info("Stored block header: %s at height %s", block_header.block_hash, block_header.height)
        except Exception as err:
            logging.error("Failed to store block header: %s", err)

    def store_transaction(self, transaction): # todo: rename to store_transaction_batch
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
            logging.info("Stored transaction: %s", transaction.transaction_hash)
        except Exception as err:
            logging.error("Failed to store transaction: %s", err)

    def store_state(self, state_root, state):
        self.state.append({state_root: state})
        logging.info("State saved: %s", state_root) # saved for when voting period ends and > 2/3 validators have signed

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
            logging.info("Stored contract state for address: %s", contract_address)
        except Exception as err:
            logging.error("Failed to store contract state: %s", err)

    def fetch_state(self, state_root):
        state_data = self.db_states.get(state_root.encode())
        return json.loads(state_data.decode()) if state_data is not None else None

    def fetch_contract_state(self, contract_address):
        contract_state_data = self.db_states.get(contract_address.encode()) # todo: db_states.get should access the correct state using the state_root key
        return json.loads(contract_state_data.decode()) if contract_state_data is not None else None
    
    def close(self):
        self.close_databases()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
wallet = Wallet()
transactionpool = TransactionPool(max_size=MAX_TX_POOL)
storage_engine = StorageEngine(transactionpool)
validation_engine = ValidationEngine(storage_engine)
tvm_engine = TinyVMEngine(storage_engine)
forger = Forger(transactionpool, storage_engine, validation_engine, tvm_engine, wallet)


# Api Endpoints

# todo: add the gossip logic
# identify the node types (validators and non-validators)
# do validator nodes gossip their signatures to non-validator nodes?
# add the endpoint responsible for requesting the signature for block "block_header.blockhash" from peer n. if the peer hasnt received the block_header
# add the endpoint for broadcasting the newly forged block_header to peers
# add the endpoint for broadcasting the signature for block_header.blockhash

async def send_transaction(request):
    data = await request.json()
    if 'transaction' in data:
        transaction_data = data['transaction']
        try:
            validate(instance=transaction_data, schema=transaction_schema)
            transaction = Transaction(**transaction_data)
            if validation_engine.validate_transaction(transaction):
                transactionpool.add_transaction(transaction)
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

app.router.add_post('/toggle_production', toggle_production)
app.router.add_post('/send_transaction', send_transaction)
app.router.add_get('/get_block/{block_hash}', get_block_by_hash)
app.router.add_get('/transactions/{transaction_hash}', get_transaction_by_hash)

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