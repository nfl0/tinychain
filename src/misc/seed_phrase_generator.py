import mnemonic
from wallet import Wallet

def generate_seed_phrase():
    mnemo = mnemonic.Mnemonic("english")
    seed_phrase = mnemo.generate(strength=256)
    return seed_phrase

if __name__ == "__main__":
    seed_phrase = generate_seed_phrase()
    print("Generated Seed Phrase:", seed_phrase)

    wallet = Wallet()
    wallet.generate_keypair_from_mnemonic(seed_phrase, "temp_wallet.dat")
    print("Generated Keypair for Seed Phrase:")
    print("Wallet address:", wallet.get_address())
