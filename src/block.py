from transaction import Transaction

block_header_schema = {
    'type': 'object',
    'properties': {
        'block_hash': {'type': 'string'},
        'height': {'type': 'number'},
        'timestamp': {'type': 'number'},
        'previous_block_hash': {'type': 'string'},
        'merkle_root': {'type': 'string'},
        'state_root': {'type': 'string'},
        'validator': {'type': 'string'},
        'signatures': {'type': 'array', 'items': {'type': 'string'}},
        'transaction_hashes': {'type': 'array', 'items': {'type': 'string'}}
    },
    'required': ['block_hash', 'height', 'timestamp', 'previous_block_hash', 'state_root', 'validator', 'signatures', 'transaction_hashes']
}

class BlockHeader:
    def __init__(self, block_hash, height, timestamp, previous_block_hash, merkle_root, state_root, validator, signatures, transaction_hashes):
        self.block_hash = block_hash
        self.height = height
        self.timestamp = timestamp
        self.previous_block_hash = previous_block_hash
        self.merkle_root = merkle_root
        self.state_root = state_root
        self.validator = validator
        self.signatures = signatures
        self.transaction_hashes = transaction_hashes

    @classmethod
    def from_dict(cls, header_data):
        return cls(
            header_data['block_hash'],
            header_data['height'],
            header_data['timestamp'],
            header_data['previous_block_hash'],
            header_data['merkle_root'],
            header_data['state_root'],
            header_data['validator'],
            header_data['signatures'],
            header_data['transaction_hashes']
        )

    def append_signature(self, validator_address, signature):
        self.signatures.append({"validator_address": validator_address, "signature": signature})

class Block:
    def __init__(self, header, transactions):
        self.header = header
        self.transactions = transactions

    @classmethod
    def from_dict(cls, block_data):
        header = BlockHeader.from_dict(block_data['header'])

        transactions = [Transaction(**t) for t in block_data.get('transactions', [])]

        return cls(header, transactions)
