import plyvel
import json
import logging
import blake3

from merkle_tree import MerkleTree
from block import BlockHeader

### System Contracts ###
accounts_contract_address = "6163636f756e7473"
staking_contract_address = "7374616b696e67"  # the word 'staking' in hex
storage_contract_address = "73746f72616765"  # the word'storage' in hex
### End of System SCs ###

tinycoin = 1000000000000000000  # 1 tinycoin = 1000000000000000000 tatoshi
genesis_addresses = [
    "374225f9043c475981d2da0fd3efbe6b8e382bb3802c062eacfabe5e0867052238ed6acaf99c5c33c1cce1a3e1ef757efd9c857417f26e2e1b5d9ab9e90c9b4d",
    "50c43f64ba255a95ab641978af7009eecef03610d120eb35035fdb0ea3c1b7f05859382f117ff396230b7cb453992d3b0da1c03f8a0572086eb938862bf6d77e",
]

db_headers = None
db_blocks = None
db_transactions = None
db_states = None
        
try:
    db_headers = plyvel.DB('headers.db', create_if_missing=True)
    db_blocks = plyvel.DB('blocks.db', create_if_missing=True)
    db_transactions = plyvel.DB('transactions.db', create_if_missing=True)
    db_states = plyvel.DB('state.db', create_if_missing=True)
except Exception as err:
    logging.error("Failed to open databases: %s", err)
    raise


def store_block(block):
    try:
        block_data = {
            'block_hash': block_header.block_hash,
            'height': block_header.height,
            'timestamp': block_header.timestamp,
            'merkle_root': block_header.merkle_root,
            'state_root': block_header.state_root,
            'previous_block_hash': block_header.previous_block_hash,
            'validator': block_header.validator,
            'signatures': block_header.signatures,
            'transactions': [transaction.to_dict() for transaction in block.transactions]
        }

        db_blocks.put(block_header.height.encode(), json.dumps(block_data).encode())
        db_headers.put(block_header.block_hash, json.dumps(block_header.to_dict()).encode())

        logging.info("Stored block: %s at height %s", block_header.block_hash, block_header.height)
    except Exception as err:
        logging.error("Failed to store block: %s", err)

def store_contract_state(contract_address, state_data):
    try:
        db_states.put(contract_address.encode(), json.dumps(state_data).encode())
        logging.info("Stored contract state for address: %s", contract_address)
    except Exception as err:
        logging.error("Failed to store contract state: %s", err)

# the genesis addresses get 1000 tinycoins account balance and 1000 staked tinycoins

merkle_tree = MerkleTree()

contract_state_cache = {}

def execute_accounts_contract(contract_state, sender, receiver, amount, operation):
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

        # Update contract state in cache
        contract_state_cache[accounts_contract_address] = contract_state
        merkle_tree.append(bytes(str(contract_state), "utf-8"))

def execute_staking_contract(contract_state, sender, amount, operation):
        if contract_state is None:
            contract_state = {}
        staked_balance = contract_state.get(sender, 0)
        if operation:
            new_staked_balance = staked_balance + amount
            contract_state[sender] = new_staked_balance
            logging.info(
                f"{sender} staked {amount} tinycoins for contract {staking_contract_address}. New staked balance: {new_staked_balance}"
            )

        # Update contract state in cache
        contract_state_cache[staking_contract_address] = contract_state
        merkle_tree.append(bytes(str(contract_state), "utf-8"))

accounts_contract_state = {}
staking_contract_state = {}
execute_accounts_contract(accounts_contract_state, "genesis", genesis_addresses[0], 10 * tinycoin, "credit")
execute_accounts_contract(accounts_contract_state, "genesis", genesis_addresses[1], 10 * tinycoin, "credit")
execute_staking_contract(staking_contract_state, genesis_addresses[0], 1000 * tinycoin, "stake")
execute_staking_contract(staking_contract_state, genesis_addresses[1], 1000 * tinycoin, "stake")

state_root = merkle_tree.root_hash().hex()
#block.state_root = state_root
store_contract_state(accounts_contract_address, accounts_contract_state)
logging.info(accounts_contract_address, ": ",accounts_contract_state)
store_contract_state(staking_contract_address, staking_contract_state)
logging.info(staking_contract_address, ": ", staking_contract_state)
print("genesis block state root: " + state_root)

def generate_block_hash(merkle_root, timestamp, state_root):
        values = [merkle_root, str(timestamp), str(state_root)]
        concatenated_string = f"{''.join(values)}".encode()
        return blake3.blake3(concatenated_string).hexdigest()

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

timestamp = int(19191919)
height = 0
# generate merkle root
valid_transactions_to_forge = None
transaction_hashes = [t.to_dict()['transaction_hash'] for t in valid_transactions_to_forge]
merkle_root = compute_merkle_root(transaction_hashes)
# generate block hash
block_hash = generate_block_hash(merkle_root, timestamp, state_root)
# genesis block dumb signatures
signatures = [{"genesis_validator1", "genesis_signature1"}, {"genesis_validator2", "genesis_signature2"}, {"genesis_validator3", "genesis_signature3"}]

block_header = BlockHeader(
    block_hash,
    height,
    timestamp,
    00000000000, # previous block
    state_root,
    0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000, # validator address
    signatures,
    transaction_hashes
)





try:
    if db_headers:
        db_headers.close()
    if db_blocks:
        db_blocks.close()
    if db_transactions:
        db_transactions.close()
    if db_states:
        db_states.close()
except Exception as err:
    logging.error("Failed to close databases: %s", err)
    raise