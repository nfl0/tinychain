import blake3
import time
from transaction import Transaction
from transaction import transaction_schema

block_header_schema = {
    'type': 'object',
    'properties': {
        'block_hash': {'type': 'string'},
        'height': {'type': 'number'},
        'timestamp': {'type': 'number'},
        'previous_block_hash': {'type': 'string'},
        'state_root': {'type': 'string'},
        'validator': {'type': 'string'},
        'signatures': {'type': 'array', 'items': {'type': 'string'}},
        'transaction_hashes': {'type': 'array', 'items': {'type': 'string'}}
    },
    'required': ['block_hash', 'height', 'timestamp', 'previous_block_hash', 'state_root', 'validator', 'signatures', 'transaction_hashes']
}

class BlockHeader:
    def __init__(self, block_hash, height, timestamp, previous_block_hash, state_root, validator, signatures, transaction_hashes):
        self.block_hash = block_hash
        self.height = height
        self.timestamp = timestamp
        self.previous_block_hash = previous_block_hash
        self.state_root = state_root
        self.validator = validator
        self.signatures = signatures
        self.transaction_hashes = transaction_hashes

class Block:
    def __init__(self, header, transactions):
        self.header = header
        self.transactions = transactions

    @classmethod
    def from_dict(cls, block_data):
        header_data = block_data.get('header', {})
        header = BlockHeader(
            header_data.get('block_hash', ''),
            header_data.get('height', 0),
            header_data.get('timestamp', int(time.time())),
            header_data.get('previous_block_hash', ''),
            header_data.get('state_root', ''),
            header_data.get('validator', ''),
            header_data.get('signatures', []),
            header_data.get('transaction_hashes', [])
        )

        transactions = [Transaction(**t) for t in block_data.get('transactions', [])]

        return cls(header, transactions)
