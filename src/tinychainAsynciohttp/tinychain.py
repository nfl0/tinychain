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
import websockets

from block import Block
from parameters import PORT, BLOCK_REWARD, BLOCK_TIME, MAX_TX_BLOCK, MAX_TX_POOL, VALIDATOR_PUBLIC_KEY

PEER_ADDR = 'ws://127.0.0.1:5001'

app = web.Application()

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
        self.message = f"{self.sender}-{self.receiver}-{self.amount}-{self.memo}"
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

class SmartContractEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine
        self.stakingContractAddress = "50c43f64ba255a95ab641978af7009eecef03610d120eb35035fdb0ea3c1b7f05859382f117ff396230b7cb453992d3b0da1c03f8a0572086eb938862bf6d77e"

    def execute_block(self, block):
        # Update validator account balance with block reward
        self.update_balance(block.validator, BLOCK_REWARD)

        # Update account balances for transactions
        for transaction in block.transactions:
            sender, receiver, amount, memo = transaction.sender, transaction.receiver, transaction.amount, transaction.memo
            self.update_balance(sender, -amount)
            self.update_balance(receiver, amount)
            if memo is not None:
                if receiver == self.stakingContractAddress: # a system-defined contract
                    if memo == "stake":
                        self.stake(sender, amount)
                    elif memo == "unstake":
                        self.unstake(sender)
                    else:
                        print("Invalid memo: 'stake' or 'unstake'")
                else:
                    logging.info(f"Memo content: {memo}")

    def update_balance(self, account_address, amount):
        current_balance = self.storage_engine.fetch_balance(account_address)
        if current_balance is None:
            current_balance = 0
        new_balance = current_balance + amount
        self.storage_engine.db_accounts.put(account_address.encode(), str(new_balance).encode())

    def stake(self, account_address, amount):
        # Load the current staking state for the account
        staking_state = self.storage_engine.fetch_contract_state(account_address)

        # Check if the account has an existing staking state
        if staking_state is None:
            staking_state = {"balance": 0}

        # Update the staking state by adding the staked amount
        staked_balance = staking_state.get("balance", 0)
        new_staked_balance = staked_balance + amount

        # Update the staking state data
        staking_state["balance"] = new_staked_balance

        # Store the updated staking state
        self.storage_engine.store_contract_state(account_address, staking_state)

        # Log the staking operation
        print(f"{account_address} staked {amount} tokens. New staked balance: {new_staked_balance}")

    def unstake(self, account_address):
        # Load the current staking state for the account
        staking_state = self.storage_engine.fetch_contract_state(account_address)

        # Check if the account has an existing staking state
        if staking_state is None:
            staking_state = {"balance": 0}

        # Get the current staked balance
        staked_balance = staking_state.get("balance", 0)

        # Check if there are staked tokens to unstake
        if staked_balance > 0:
            # Perform the unstaking operation (e.g., release locked tokens)
            # Here, we'll assume that the entire staked balance is released.
            # You can implement more complex unstaking logic as needed.
            released_balance = staked_balance

            # Update the staking state data after unstaking
            staking_state["balance"] = 0  # Reset staked balance to zero

            # Store the updated staking state
            self.storage_engine.store_contract_state(account_address, staking_state)

            # Add the released balance back to the account's balance
            self.update_balance(account_address, released_balance)

            # Log the unstaking operation
            print(f"{account_address} unstaked {released_balance} tokens. Staked balance reset to zero.")
        else:
            # No staked tokens to unstake
            print(f"{account_address} has no staked tokens to unstake.")

    def update_contract_state(self, contract_address, state_data):
        current_state = self.storage_engine.fetch_contract_state(contract_address)
        if current_state is None:
            current_state = {}
        current_state.update(state_data)
        self.storage_engine.store_contract_state(contract_address, current_state)


class StorageEngine:
    def __init__(self):
        self.db_blocks = None
        self.db_accounts = None
        self.db_states = None
        self.last_block_hash = None

    def open_databases(self):
        try:
            self.db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
            self.db_accounts = plyvel.DB('accounts.db', create_if_missing=True)
            self.db_states = plyvel.DB('contract_states.db', create_if_missing=True)
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
            
            contract_engine.execute_block(block)

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
contract_engine = SmartContractEngine(storage_engine)

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
