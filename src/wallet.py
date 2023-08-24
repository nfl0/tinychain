import requests
import ecdsa
import hashlib
import json

# Generate a new key pair
private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
public_key = private_key.get_verifying_key()

def create_transaction(sender, receiver, amount):
    transaction = {
        'sender': sender.hex(),
        'receiver': receiver.hex(),
        'amount': amount,
    }
    message = f"{transaction['sender']}-{transaction['receiver']}-{transaction['amount']}"
    signature = private_key.sign(message.encode()).hex()
    transaction['signature'] = signature
    transaction['message'] = message
    return transaction

def send_transaction(transaction):
    data = {
        'transaction': transaction
    }
    response = requests.post('http://192.168.0.111:5000/send_transaction', json=data)
    return response.json()

if __name__ == '__main__':
    sender_address = public_key.to_string()
    receiver_address = public_key.to_string()  # Sending to self for testing
    amount = 10  # Amount to send
    
    transaction = create_transaction(sender_address, receiver_address, amount)
    print("Created Transaction:", transaction)

    response = send_transaction(transaction)
    print("Transaction Response:", response)
