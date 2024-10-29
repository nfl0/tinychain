import os
import ecdsa
import pickle
from mnemonic import Mnemonic

WALLET_PATH = './wallet/'
WALLET_FILE = 'wallet.dat'

def generate_mnemonic():
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=256)

def generate_keypair_from_mnemonic(mnemonic):
    seed = Mnemonic.to_seed(mnemonic)
    private_key = ecdsa.SigningKey.from_string(seed[:32], curve=ecdsa.SECP256k1)
    public_key = private_key.get_verifying_key()
    return private_key, public_key

def save_wallet(private_key, filename):
    with open(os.path.join(WALLET_PATH, filename), "wb") as file:
        pickle.dump(private_key, file)

def wallet_exists(filename):
    return os.path.exists(os.path.join(WALLET_PATH, filename))

def main():
    os.makedirs(WALLET_PATH, exist_ok=True)

    if wallet_exists(WALLET_FILE):
        print(f"Wallet already exists at {WALLET_PATH + WALLET_FILE}.")
        print("Aborting to prevent overwrite.")
        return

    mnemonic = generate_mnemonic()
    private_key, public_key = generate_keypair_from_mnemonic(mnemonic)

    save_wallet(private_key, WALLET_FILE)

    print("Mnemonic:", mnemonic)
    print("Private Key:", private_key.to_string().hex())
    print("Public Key:", public_key.to_string().hex())

if __name__ == "__main__":
    main()
