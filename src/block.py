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
        'proposer': {'type': 'string'},
        'signatures': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'validator_address': {'type': 'string'},
                    'timestamp': {'type': 'number'},
                    'signature_data': {'type': 'string'}
                },
                'required': ['validator_address', 'timestamp', 'signature_data']
            }
        },
        'transaction_hashes': {'type': 'array', 'items': {'type': 'string'}}
    },
    'required': ['block_hash', 'height', 'timestamp', 'previous_block_hash', 'state_root', 'proposer', 'signatures', 'transaction_hashes']
}

class Signature:
    def __init__(self, validator_address, timestamp, signature_data):
        self.validator_address = validator_address
        self.timestamp = timestamp
        self.signature_data = signature_data

    @classmethod
    def from_dict(cls, signature_data):
        return cls(
            signature_data['validator_address'],
            signature_data['timestamp'],
            signature_data['signature_data']
        )

    def to_dict(self):
        return {
            'validator_address': self.validator_address,
            'timestamp': self.timestamp,
            'signature_data': self.signature_data
        }

class BlockHeader:
    def __init__(self, block_hash, height, timestamp, previous_block_hash, merkle_root, state_root, proposer, signatures, transaction_hashes):
        self.block_hash = block_hash
        self.height = height
        self.timestamp = timestamp
        self.previous_block_hash = previous_block_hash
        self.merkle_root = merkle_root
        self.state_root = state_root
        self.proposer = proposer
        self.signatures = [Signature.from_dict(sig) for sig in signatures]
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
            header_data['proposer'],
            header_data['signatures'],
            header_data['transaction_hashes']
        )

    def append_signature(self, validator_address, signature_data):
        timestamp = int(time.time())
        signature = Signature(validator_address, timestamp, signature_data)
        self.signatures.append(signature)

class Block:
    def __init__(self, header, transactions):
        self.header = header
        self.transactions = transactions

    @classmethod
    def from_dict(cls, block_data):
        header = BlockHeader.from_dict(block_data['header'])

        transactions = [Transaction(**t) for t in block_data.get('transactions', [])]

        return cls(header, transactions)
