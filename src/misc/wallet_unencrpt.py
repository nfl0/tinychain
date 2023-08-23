import requests
import json

class Wallet:
    def __init__(self, address):
        self.address = address

    def send_transaction(self, receiver, amount, private_key):
        transaction = {
            'sender': self.address,
            'receiver': receiver,
            'amount': amount,
            'signature': self.sign_transaction(private_key)
        }

        response = requests.post('http://192.168.0.111:5000/send_transaction', json={'transaction': transaction})
        data = response.json()

        return data

    def sign_transaction(self, private_key):
        # In a real scenario, you would use cryptographic signing here
        # For simplicity, let's assume private_key is the signature
        return private_key

    def get_balance(self):
        response = requests.get(f'http://192.168.0.111:5000/balance/{self.address}')
        data = response.json()

        return data

if __name__ == '__main__':
    wallet_address = 'your_wallet_address'
    private_key = 'your_private_key'

    wallet = Wallet(wallet_address)

    while True:
        print("Choose an option:")
        print("1. Send transaction")
        print("2. Check balance")
        print("3. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            receiver = input("Enter receiver's address: ")
            amount = float(input("Enter amount: "))

            response = wallet.send_transaction(receiver, amount, private_key)
            print(response)

        elif choice == '2':
            balance = wallet.get_balance()
            if balance is not None:
                print(f"Balance: {balance['balance']}")
            else:
                print("Account not found.")

        elif choice == '3':
            break

        else:
            print("Invalid choice. Please choose again.")
