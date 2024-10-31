import blake3
import time
from block import BlockHeader, Block, Signature
from peer_communication import broadcast_block_header
from vm import TinyVMEngine

class Forger:
    def __init__(self, transactionpool, storage_engine, validation_engine, wallet):
        self.transactionpool = transactionpool
        self.storage_engine = storage_engine
        self.validation_engine = validation_engine

        self.wallet = wallet
        self.validator = self.proposer = self.wallet.get_address()
        self.sign = self.wallet.sign_message

        self.production_enabled = True

        self.in_memory_blocks = {}
        self.in_memory_block_headers = {}
        self.current_proposer_index = 0

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

    def forge_new_block(self, replay=True, block_header=None):
        if not self.production_enabled:
            return "Forging is disabled"

        transactions_to_forge = []

        if replay:
            for transaction_hash in block_header.transaction_hashes:
                transaction = self.transactionpool.get_transaction_by_hash(transaction_hash)
                if transaction is not None:
                    transactions_to_forge.append(transaction)
                else:
                    logging.info(f"Transaction {transaction_hash} not found in pool, requesting transaction from peers...")
                    # todo: request transaction from connected peers (or the block producer?)
        else:
            transactions_to_forge = self.transactionpool.get_transactions()

        valid_transactions_to_forge = [t for t in transactions_to_forge if self.validation_engine.validate_transaction(t)]

        previous_block_header = self.storage_engine.fetch_last_block_header()
        previous_block_hash = previous_block_header.block_hash
        height = previous_block_header.height + 1
        current_state = self.storage_engine.fetch_state(previous_block_header.state_root)

        tvm_engine = TinyVMEngine(current_state)

        if not replay:
            self.proposer = self.wallet.get_address()
            timestamp = int(time.time())
            state_root, new_state = tvm_engine.exec(valid_transactions_to_forge, self.proposer)
            transaction_hashes = [t.to_dict()['transaction_hash'] for t in valid_transactions_to_forge]
            merkle_root = self.compute_merkle_root(transaction_hashes)
            block_hash = self.generate_block_hash(merkle_root, timestamp, state_root, previous_block_hash)
            signature = self.sign(block_hash)
            validator_index = self.get_validator_index(self.proposer)
            signatures = [Signature(self.proposer, timestamp, signature, validator_index)]
        else:
            state_root, new_state = tvm_engine.exec(valid_transactions_to_forge, block_header.proposer)
            if state_root == block_header.state_root:
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
        
        block = Block(block_header, valid_transactions_to_forge)

        self.in_memory_blocks[block.header.block_hash] = block
        self.in_memory_block_headers[block.header.block_hash] = block_header

        broadcast_block_header(block_header)

        if self.has_enough_signatures(block_header):
            self.storage_engine.store_block(block)
            self.storage_engine.store_block_header(block_header)
            self.storage_engine.store_state(block.header.state_root, new_state)
            return True
        else:
            del self.in_memory_blocks[block.header.block_hash]
            del self.in_memory_block_headers[block.header.block_hash]
            return False

    def has_enough_signatures(self, block_header):
        return True

    def get_validator_index(self, validator_address):
        staking_contract_state = self.storage_engine.fetch_contract_state("7374616b696e67")
        if staking_contract_state and validator_address in staking_contract_state:
            return staking_contract_state[validator_address]['index']
        return -1
