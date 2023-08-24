import binascii
import ecdsa
from ecdsa import VerifyingKey

def is_valid_public_key(public_key):
    try:
        public_key_bytes = bytes.fromhex(public_key)
        vk = VerifyingKey.from_string(public_key_bytes, curve=ecdsa.SECP256k1)
        return True
    except (ValueError, binascii.Error, ecdsa.keys.BadPublicKeyError):
        return False

miner_public_key = '99628359a19dcba4c0400423478c3006d6fbcc8d0c0564db8d6cca5d4dfad7aaadf648e5d677ebc82a31d0c8045bd094a25b6f6984806638ac0b29fcfdb509d6'

if is_valid_public_key(miner_public_key):
    print("Miner's public key is valid.")
else:
    print("Miner's public key is invalid.")
