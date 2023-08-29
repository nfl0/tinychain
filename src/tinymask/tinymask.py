# tinymask.py - Official full-fledged software wallet for the tinychain blockchain

import tinychain
import wallet

class Tinymask:
    def __init__(self):
        self.tinychain = tinychain.Tinychain()
        self.wallet = wallet.Wallet()

    def create_account(self):
        return self.wallet.create_account()

    def get_balance(self, address):
        return self.tinychain.get_balance(address)

    def send_transaction(self, sender, recipient, amount):
        return self.tinychain.send_transaction(sender, recipient, amount)

    def mine_block(self):
        return self.tinychain.mine_block()

    def get_blockchain(self):
        return self.tinychain.get_blockchain()

    def get_transaction_pool(self):
        return self.tinychain.get_transaction_pool()

    def get_pending_transactions(self):
        return self.tinychain.get_pending_transactions()

    def get_transaction(self, transaction_id):
        return self.tinychain.get_transaction(transaction_id)

    def get_transaction_history(self, address):
        return self.tinychain.get_transaction_history(address)

    def get_wallet_balance(self):
        return self.wallet.get_balance()

    def get_wallet_address(self):
        return self.wallet.get_address()

    def export_wallet(self, password):
        return self.wallet.export_wallet(password)

    def import_wallet(self, wallet_data, password):
        return self.wallet.import_wallet(wallet_data, password)

    def sign_transaction(self, transaction, password):
        return self.wallet.sign_transaction(transaction, password)

    def verify_transaction_signature(self, transaction):
        return self.wallet.verify_transaction_signature(transaction)

    def validate_transaction(self, transaction):
        return self.tinychain.validate_transaction(transaction)

    def validate_block(self, block):
        return self.tinychain.validate_block(block)

    def run(self):
        # Start the tinychain node
        self.tinychain.run()

        # Start the wallet interface
        self.wallet.run()

if __name__ == "__main__":
    tinymask = Tinymask()
    tinymask.run()
