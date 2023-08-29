# tinymask.py - Official Full-Fledged Software Wallet for Tinychain Blockchain

import requests

class Tinymask:
    def __init__(self, node_url):
        self.node_url = node_url

    def get_balance(self, address):
        url = f"{self.node_url}/balance/{address}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def send_transaction(self, sender, recipient, amount):
        url = f"{self.node_url}/transaction"
        data = {
            "sender": sender,
            "recipient": recipient,
            "amount": amount
        }
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    # Add more methods for interacting with the Tinychain blockchain API

# Example usage
if __name__ == "__main__":
    node_url = "http://localhost:5000"  # Replace with the actual node URL
    wallet = Tinymask(node_url)
    balance = wallet.get_balance("address")
    print(balance)
