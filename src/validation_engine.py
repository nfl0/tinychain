import ecdsa
from ecdsa import VerifyingKey
import time
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

    def validate_block(self, block, previous_block):
        if not isinstance(block, Block):
            return False
        
        if not self.is_valid_block_hash(block.block_hash):
            return False

        if block.previous_block_hash != previous_block.block_hash:
            return False
        
        if not self.is_valid_block_hash(block.previous_block_hash):
            return False

        if block.height != previous_block.height + 1:
            print("block.height != previous_block.height + 1")
            return False

        time_tolerance = 2
        current_time = int(time.time())
        if not (previous_block.timestamp < block.timestamp < current_time + time_tolerance):
            return False

        computed_hash = block.generate_block_hash()
        if block.block_hash != computed_hash:
            print("block.block_hash != computed_hash")
            return False

        # Calculate the Merkle root of the block's transactions
        computed_merkle_root = block.calculate_merkle_root()

        if block.merkle_root != computed_merkle_root:
            print("block.merkle_root != computed_merkle_root")
            return False

        for transaction in block.transactions:
            if not self.validate_transaction(transaction):
                return False

        return True