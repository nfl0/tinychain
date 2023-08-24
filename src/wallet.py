import requests
import ecdsa
import hashlib
import json
import pickle
import os

def generate_keypair(filename):
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    public_key = private_key.get_verifying_key()
    with open(filename, "wb") as file:
        pickle.dump(private_key, file)
    return private_key, public_key

def create_transaction(sender, receiver, amount, sender_key):
    transaction = {
        'sender': sender.hex(),
        'receiver': receiver.hex(),
        'amount': amount,
    }
    message = f"{transaction['sender']}-{transaction['receiver']}-{transaction['amount']}"
    signature = sender_key.sign(message.encode()).hex()
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
    while True:
        print("Select an option:")
        print("1. Generate New Wallet")
        print("2. Send Funds")
        print("3. Exit")
        option = int(input())

        if option == 1:
            wallet_name = input("Enter wallet name (e.g., wallet1.dat): ")
            private_key, public_key = generate_keypair(wallet_name)
            print(f"New wallet '{wallet_name}' generated.")

        elif option == 2:
            wallet_files = [f for f in os.listdir() if f.startswith("wallet") and f.endswith(".dat")]
            if not wallet_files:
                print("No wallets found. Generate wallets first.")
                continue

            print("Select sending wallet:")
            for idx, wallet_file in enumerate(wallet_files):
                print(f"{idx + 1}. {wallet_file}")
            sending_option = int(input()) - 1

            if sending_option < 0 or sending_option >= len(wallet_files):
                print("Invalid option.")
                continue

            sending_wallet = wallet_files[sending_option]
            with open(sending_wallet, "rb") as file:
                private_key = pickle.load(file)
                public_key = private_key.get_verifying_key()
                sender_address = public_key.to_string()

            print("Select receiving account:")
            for idx, wallet_file in enumerate(wallet_files):
                print(f"{idx + 1}. {wallet_file}")
            receiving_option = int(input()) - 1

            if receiving_option < 0 or receiving_option >= len(wallet_files):
                print("Invalid option.")
                continue

            receiving_wallet = wallet_files[receiving_option]
            with open(receiving_wallet, "rb") as file:
                receiving_public_key = pickle.load(file).get_verifying_key()
                receiver_address = receiving_public_key.to_string()

            amount = int(input("Enter amount to send:"))

            transaction = create_transaction(sender_address, receiver_address, amount, private_key)
            print("Created Transaction:", transaction)

            response = send_transaction(transaction)
            print("Transaction Response:", response)

        elif option == 3:
            print("Exiting.")
            break

        else:
            print("Invalid option. Please select a valid option.")
