from Crypto.PublicKey import RSA
from Crypto.Hash import keccak

# Generate a new RSA key pair
key = RSA.generate(2048)

# Get the public key in PEM format
public_key_pem = key.publickey().export_key(format='PEM')

# Calculate the keccak hash of the public key
keccak_hash = keccak.new(digest_bits=256)
keccak_hash.update(public_key_pem)
public_key_hash = keccak_hash.digest()

# Ethereum address is the last 20 bytes (40 hexadecimal characters) of the keccak hash
ethereum_address = '0x' + public_key_hash[-20:].hex()

print("Public Key (PEM):")
print(public_key_pem.decode('utf-8'))
print("\nEthereum Address:")
print(ethereum_address)
