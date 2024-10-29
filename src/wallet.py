import ecdsa
import pickle
import os
import hashlib
import hmac
import binascii
import mnemonic

WALLET_PATH = './wallet/'

class Wallet:
    def __init__(self):
        if not os.path.exists(os.path.join(WALLET_PATH, "wallet.dat")):
            self.initialize_wallet()

    def generate_keypair(self, filename):
        private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        with open(os.path.join(WALLET_PATH, filename), "wb") as file:
            pickle.dump(private_key, file)
        return True

    def generate_keypair_from_mnemonic(self, mnemonic_seed, filename):
        seed = mnemonic.Mnemonic.to_seed(mnemonic_seed)
        private_key = ecdsa.SigningKey.from_string(seed[:32], curve=ecdsa.SECP256k1)
        with open(os.path.join(WALLET_PATH, filename), "wb") as file:
            pickle.dump(private_key, file)
        return True

    def sign_message(self, message):
        with open(os.path.join(WALLET_PATH, "wallet.dat"), "rb") as file:
            private_key = pickle.load(file)
            signature = private_key.sign(message.encode()).hex()
            return signature
    
    def get_address(self):
        with open(os.path.join(WALLET_PATH, "wallet.dat"), "rb") as file:
            private_key = pickle.load(file)
            public_key = private_key.get_verifying_key()
            return public_key.to_string().hex()

    def verify_signature(self, message, signature, public_key_hex=None):
        if public_key_hex == None:
            public_key_hex = self.get_address()
        public_key = ecdsa.VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=ecdsa.SECP256k1)
        message = message.encode()
        try:
            return public_key.verify(bytes.fromhex(signature), message)
        except ecdsa.BadSignatureError:
            return False

    def initialize_wallet(self):
        mnemonic_seed = input("Enter a mnemonic seed to initialize the wallet: ")
        self.generate_keypair_from_mnemonic(mnemonic_seed, "wallet.dat")
        print("New wallet generated! Please fund it with some coins.")
        print("Wallet address:", self.get_address())

os.makedirs(WALLET_PATH, exist_ok=True)
if not os.path.exists(os.path.join(WALLET_PATH, "wallet.dat")):
    wallet = Wallet()
    wallet.generate_keypair("wallet.dat")
    print("New wallet generated! Please fund it with some coins.")
    print("Wallet address:", wallet.get_address())
