import mnemonic

def generate_seed_phrase():
    mnemo = mnemonic.Mnemonic("english")
    seed_phrase = mnemo.generate(strength=256)
    return seed_phrase

if __name__ == "__main__":
    seed_phrase = generate_seed_phrase()
    print("Generated Seed Phrase:", seed_phrase)
