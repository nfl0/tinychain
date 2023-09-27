import ecdsa
from ecdsa import VerifyingKey
import time
import blake3
import re # todos: validate previous_bock_hash against regex.  

from wallet import Wallet
from block import Block

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def is_valid_address(self, address):
        return bool(re.match(r'^[0-9a-fA-F]+$', address))

    def is_valid_block_hash(self, block_hash):
        return bool(re.match(r'^[0-9a-fA-F]+$', block_hash))

    def validate_transaction(self, transaction):

        if transaction.fee <= 0:
            return False

        expected_nonce = self.storage_engine.get_nonce_for_account(transaction.sender)
        if transaction.nonce != expected_nonce:
            return False

        if not self.is_valid_address(transaction.sender):
            return False

        if not self.is_valid_address(transaction.receiver):
            return False

        if transaction.amount <= 0:
            return False
        
        if len(transaction.memo) > 256:
            return False

        sender_balance = self.storage_engine.fetch_balance(transaction.sender)
        if sender_balance is None or sender_balance < transaction.amount:
            return False

        # todos: validate signature.
        #if not Wallet.verify_signature(transaction.sender, transaction.signature, transaction.message):
        #    return False
        if not self.verify_transaction_signature(transaction):
            return False

        return True

    def verify_transaction_signature(self, transaction):
        public_key = transaction.sender
        signature = transaction.signature
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=ecdsa.SECP256k1)
        try:
            vk.verify(bytes.fromhex(signature), transaction.message.encode())
            return True
        except ecdsa.BadSignatureError:
            return False

    def validate_block_header(self, block, previous_block_header):
        if not isinstance(block, Block):
            return False
        
        if not self.is_valid_block_hash(previous_block_header.block_hash):
            return False

        if not self.is_valid_block_hash(block.header.block_hash):
            return False

        if block.header.previous_block_hash != previous_block_header.block_hash:
            return False

        if block.header.height != previous_block_header.height + 1:
            print("block.height != previous_block.height + 1")
            return False

        time_tolerance = 2
        current_time = int(time.time())
        if not (previous_block_header.timestamp < block.header.timestamp < current_time + time_tolerance):
            return False

        values = [block.header.merkle_root, str(block.header.timestamp), str(block.header.state_root), previous_block_header.block_hash]
        concatenated_string = ''.join(values).encode()
        computed_hash = blake3.blake3(concatenated_string).hexdigest()
        if block.header.block_hash != computed_hash:
            print("block.block_hash != computed_hash")
            return False

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

        transaction_hashes = [t.to_dict()['transaction_hash'] for t in block.transactions]

        # Calculate the Merkle root of the block's transactions
        if len(transaction_hashes) == 0:
            computed_merkle_root = blake3.blake3(b'').hexdigest()

        if len(transaction_hashes) > 0:

            while len(transaction_hashes) > 1:
                if len(transaction_hashes) % 2 != 0:
                    transaction_hashes.append(transaction_hashes[-1])
                transaction_hashes = [blake3.blake3(transaction_hashes[i].encode() + transaction_hashes[i + 1].encode()).digest() for i in range(0, len(transaction_hashes), 2)]

            if isinstance(transaction_hashes[0], str):
                # If it's a string, encode it as bytes using UTF-8
                transaction_hashes[0] = transaction_hashes[0].encode('utf-8')

        computed_merkle_root = blake3.blake3(transaction_hashes[0]).hexdigest()

        if block.header.merkle_root != computed_merkle_root:
            print("block.merkle_root != computed_merkle_root")
            return False

        # verify the signature
        if Wallet.verify_signature(block.header.block_hash, block.header.signature, block.header.validator):
            return False

        for transaction in block.header.transactions:
            if not self.validate_transaction(transaction):
                return False

        return True
    


# validate(sample_block_data['header'], block_header_schema)