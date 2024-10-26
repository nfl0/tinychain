import requests
import ecdsa
import pickle
import os
import time

API_URL = 'http://127.0.0.1:5000'  # Update to the correct API URL
WALLET_PATH = './wallets/'
TRANSACTION_FEE = 10  # Hardcoded transaction fee

def generate_keypair(filename):
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    public_key = private_key.get_verifying_key()
    with open(os.path.join(WALLET_PATH, filename), "wb") as file:
        pickle.dump(private_key, file)
    return private_key, public_key

def create_transaction(sender, receiver, amount, memo, sender_key, nonce):
    transaction = {
        'sender': sender.hex(),
        'receiver': receiver.hex(),
        'amount': amount,
        'memo': memo,
        'fee': TRANSACTION_FEE,
        'nonce': nonce
    }
    signature = sender_key.sign(f"{transaction['sender']}-{transaction['receiver']}-{transaction['amount']}-{transaction['memo']}-{transaction['fee']}-{transaction['nonce']}".encode()).hex()
    transaction['signature'] = signature
    return transaction

def send_transaction(transaction):
    data = {
        'transaction': transaction
    }
    response = requests.post(f'{API_URL}/send_transaction', json=data)
    return response.json()

def get_balance(address):
    response = requests.get(f'{API_URL}/get_balance/{address.hex()}')
    return response.json()

def get_nonce(address):
    response = requests.get(f'{API_URL}/get_nonce/{address.hex()}')
    return response.json().get('nonce', 0)

def print_wallet_menu():
    print("Select an option:")
    print("1. Generate New Wallet")
    print("2. Send Funds")
    print("3. Send to Custom Address")
    print("4. Send Preset Transactions")
    print("5. Exit")

if __name__ == '__main__':
    os.makedirs(WALLET_PATH, exist_ok=True)

    while True:
        print_wallet_menu()
        option = int(input())

        if option == 1:
            wallet_name = input("Enter wallet name (e.g., wallet1.dat): ")
            private_key, public_key = generate_keypair(wallet_name)
            print(f"New wallet '{wallet_name}' generated.")

        elif option == 2 or option == 3:
            wallet_files = [f for f in os.listdir(WALLET_PATH) if f.startswith("wallet") and f.endswith(".dat")]
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
            with open(os.path.join(WALLET_PATH, sending_wallet), "rb") as file:
                private_key = pickle.load(file)
                public_key = private_key.get_verifying_key()
                sender_address = public_key.to_string()

            nonce = get_nonce(sender_address)

            if option == 2:
                print("Select receiving account:")
                for idx, wallet_file in enumerate(wallet_files):
                    print(f"{idx + 1}. {wallet_file}")
                receiving_option = int(input()) - 1

                if receiving_option < 0 or receiving_option >= len(wallet_files):
                    print("Invalid option.")
                    continue

                receiving_wallet = wallet_files[receiving_option]
                with open(os.path.join(WALLET_PATH, receiving_wallet), "rb") as file:
                    receiving_public_key = pickle.load(file).get_verifying_key()
                    receiver_address = receiving_public_key.to_string()

                amount = int(input("Enter amount to send:"))
                memo = ""

                transaction = create_transaction(sender_address, receiver_address, amount, memo, private_key, nonce)
                print("Created Transaction:", transaction)

                response = send_transaction(transaction)
                print("Transaction Response:", response)

            elif option == 3:
                input_string = input("Enter custom address:")
                hex_chunks = [input_string[i:i+2] for i in range(0, len(input_string), 2)]

                custom_address = bytes.fromhex(''.join(hex_chunks))

                amount = int(input("Enter amount to send:"))
                memo = "stake"

                transaction = create_transaction(sender_address, custom_address, amount, memo, private_key, nonce)
                print("Created Transaction:", transaction)

                response = send_transaction(transaction)
                print("Transaction Response:", response)
        elif option == 4:
            wallet_files = [f for f in os.listdir(WALLET_PATH) if f.startswith("wallet") and f.endswith(".dat")]
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
            with open(os.path.join(WALLET_PATH, sending_wallet), "rb") as file:
                private_key = pickle.load(file)
                public_key = private_key.get_verifying_key()
                sender_address = public_key.to_string()

            nonce = get_nonce(sender_address)

            for _ in range(2):  # Send two preset transactions
                transactions = [
                    {
                        'sender': sender_address.hex(),
                        'receiver': "7374616b696e67",
                        'amount': 1,
                        'memo': 'stake'
                    }
                ]

                for transaction in transactions:
                    receiver_address = bytes.fromhex(transaction['receiver'])
                    memo = transaction['memo']
                    amount = transaction['amount']
                    formatted_transaction = create_transaction(sender_address, receiver_address, amount, memo, private_key, nonce)
                    
                    response = send_transaction(formatted_transaction)
                    print("Transaction Response:", response)

                time.sleep(11)  # Wait for half a second before sending the next preset transactions

            print("Preset transactions sent to custom addresses.")
        elif option == 5:
            print("Exiting.")
            break

        else:
            print("Invalid option. Please select a valid option.")
