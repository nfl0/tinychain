import ecdsa
from ecdsa import VerifyingKey
import time
#from block import Block
import re # todos: validate previous_bock_hash against regex. also, check transaction.amount > 0 

class ValidationEngine:
    def __init__(self, storage_engine):
        self.storage_engine = storage_engine

    def is_valid_address(self, address):
        return bool(re.match(r'^[0-9a-fA-F]+$', address))

    def validate_transaction(self, transaction):
        sender_balance = self.storage_engine.fetch_balance(transaction.sender)
        if (
            sender_balance is not None
            and sender_balance >= transaction.amount
            and self.verify_transaction_signature(transaction)
            and self.is_valid_address(transaction.sender)
            and self.is_valid_address(transaction.receiver)
            and transaction.amount > 0
        ):
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
        #if not isinstance(block, Block):
        #    return False

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