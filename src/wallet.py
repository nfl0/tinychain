import os
import json
import requests
import blake3
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa

# Set the Flask app address and port
APP_ADDRESS = 'http://127.0.0.1:5000'

# Generate or load wallet keys
def generate_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    return private_key_pem, public_key_pem

def load_keys():
    if os.path.exists('wallet.dat'):
        with open('wallet.dat', 'r') as f:
            keys = json.load(f)
            private_key_pem = keys['private_key']
            public_key_pem = keys['public_key']
            return private_key_pem, public_key_pem
    else:
        private_key_pem, public_key_pem = generate_keys()
        keys = {
            'private_key': private_key_pem,
            'public_key': public_key_pem
        }
        with open('wallet.dat', 'w') as f:
            json.dump(keys, f)
        return private_key_pem, public_key_pem

def sign_transaction(private_key, data):
    private_key = serialization.load_pem_private_key(
        private_key.encode(),
        password=None
    )
    signature = private_key.sign(
        data.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature

def send_transaction(sender_private_key, sender_public_key, receiver_address, amount):
    transaction_data = {
        'sender': sender_public_key,
        'receiver': receiver_address,
        'amount': amount,
    }
    data_to_sign = json.dumps(transaction_data, sort_keys=True)
    signature = sign_transaction(sender_private_key, data_to_sign)
    transaction_data['signature'] = signature.hex()
    response = requests.post(f'{APP_ADDRESS}/send_transaction', json={'transaction': transaction_data})
    return response.json()

if __name__ == '__main__':
    private_key, public_key = load_keys()
    print("Your public key:")
    print(public_key)
    
    while True:
        print("\n1. Send Transaction")
        print("2. Exit")
        choice = input("Enter your choice: ")
        
        if choice == '1':
            receiver_address = input("Enter receiver's public key: ")
            amount = float(input("Enter amount: "))
            response = send_transaction(private_key, public_key, receiver_address, amount)
            print(response)
        elif choice == '2':
            break
