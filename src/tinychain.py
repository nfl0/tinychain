from aiohttp import web
import asyncio
import logging
import ecdsa
from ecdsa import VerifyingKey
import plyvel
import json
from jsonschema import validate
import jsonschema
import blake3
import time
import websockets

from parameters import HTTP_PORT, RPC_PORT, BLOCK_REWARD, BLOCK_TIME, MAX_TX_BLOCK, MAX_TX_POOL, VALIDATOR_PUBLIC_KEY

connectedPeers = ['192.168.0.111', '192.168.0.112'] # store the blockchain and relays transactions

app = web.Application()


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

    def validate_block(self, block, previous_block=None):
        if not isinstance(block, Block):
            return False

        # If there is no previous block, allow the first block to pass validation
        if previous_block is None:
            return True

        if block.height != previous_block.height + 1:
            return False

        time_tolerance = 2
        current_time = int(time.time())
        if not (previous_block.timestamp < block.timestamp < current_time + time_tolerance):
            return False

        computed_hash = block.generate_block_hash()
        if block.block_hash != computed_hash:
            return False

        for transaction in block.transactions:
            if not self.validate_transaction(transaction):
                return False

        return True

class Block:
    def __init__(self, height, transactions, validator_address, previous_block_hash=None, timestamp=None):
        self.height = height
        self.transactions = transactions
        self.timestamp = timestamp or int(time.time())
        self.validator = validator_address
        self.previous_block_hash = previous_block_hash
        self.block_hash = self.generate_block_hash()

    def generate_block_hash(self):
        sorted_transaction_hashes = sorted([t.to_dict()['transaction_hash'] for t in self.transactions])
        values = sorted_transaction_hashes + [str(self.timestamp)]
        if self.previous_block_hash:
            values.append(str(self.previous_block_hash))
        return blake3.blake3(''.join(values).encode()).hexdigest()
    
    @classmethod
    def from_dict(cls, block_data):
        height = block_data['height']
        transactions = [Transaction(**t) for t in block_data['transactions']]
        timestamp = block_data['timestamp']
        validator_address = block_data['validator']
        previous_block_hash = block_data['previous_block_hash']
        return cls(height, transactions, validator_address, previous_block_hash, timestamp)

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

class TinyVMEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine
        ### System Contracts ###
        self.accounts_contract_address = "6163636f756e7473"
        self.staking_contract_address = "7374616b696e67"
        ### End of System SCs ###

    def execute_block(self, block):
        # Fetch the accounts contract state from storage
        accounts_contract_state = self.storage_engine.fetch_contract_state(self.accounts_contract_address)
        
        # Update validator account balance with block reward
        self.execute_accounts_contract(accounts_contract_state, block.validator, None, BLOCK_REWARD, "credit")

        for transaction in block.transactions:
            sender, receiver, amount, memo = (
                transaction.sender,
                transaction.receiver,
                transaction.amount,
                transaction.memo,
            )

            self.execute_accounts_contract(accounts_contract_state, sender, receiver, amount, "transfer")

            if receiver == self.staking_contract_address:
                if memo in ("stake", "unstake"):
                    staking_contract_state = self.storage_engine.fetch_contract_state(self.staking_contract_address)
                    is_stake = memo == "stake"
                    self.execute_staking_contract(staking_contract_state, sender, amount, is_stake)
                else:
                    logging.info("Invalid memo. Try 'stake' or 'unstake'")

    def execute_accounts_contract(self, contract_state, sender, receiver, amount, operation):
        if contract_state is None:
            contract_state = {}
        if operation == "credit":
            current_balance = contract_state.get(sender, 0)
            new_balance = current_balance + amount
            contract_state[sender] = new_balance
        elif operation == "transfer":
            sender_balance = contract_state.get(sender, 0)
            receiver_balance = contract_state.get(receiver, 0)
            if sender_balance >= amount:
                contract_state[sender] = sender_balance - amount
                contract_state[receiver] = receiver_balance + amount
            else:
                logging.info(f"Insufficient balance for sender: {sender}")

        self.store_contract_state(self.accounts_contract_address, contract_state)

    def execute_staking_contract(self, contract_state, sender, amount, operation):
        if contract_state is None:
            contract_state = {}
        staked_balance = contract_state.get(sender, 0)
        if operation:
            new_staked_balance = staked_balance + amount
            contract_state[sender] = new_staked_balance
            logging.info(
                f"{sender} staked {amount} tinycoins for contract {self.staking_contract_address}. New staked balance: {new_staked_balance}"
            )
        else:
            if staked_balance > 0:
                released_balance = staked_balance
                contract_state[sender] = 0
                self.execute_accounts_contract(contract_state, sender, None, released_balance, "credit")
                logging.info(
                    f"{sender} unstaked {released_balance} tinycoins for contract {self.staking_contract_address}. Staked balance reset to zero."
                )
            else:
                logging.info(
                    f"{sender} has no staked tinycoins for contract {self.staking_contract_address} to unstake."
                )
                
        self.store_contract_state(self.staking_contract_address, contract_state)

    def get_contract_state(self, contract_address):
        return self.storage_engine.fetch_contract_state(contract_address)

    def store_contract_state(self, contract_address, state_data):
        self.storage_engine.store_contract_state(contract_address, state_data)

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
        # Fetch the balance from the accounts contract state
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
