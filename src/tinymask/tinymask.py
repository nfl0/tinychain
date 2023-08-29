# tinymask.py - Official Full-Fledged Software Wallet for Tinychain Blockchain

import requests
import random
import string
import tkinter as tk
from tkinter import messagebox

class Tinymask:
    def __init__(self, node_url):
        self.node_url = node_url

    def generate_keypair(self):
        private_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        public_key = private_key + "-pub"
        return private_key, public_key

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

def generate_keypair():
    wallet = Tinymask(node_url)
    private_key, public_key = wallet.generate_keypair()
    messagebox.showinfo("Keypair Generated", f"Private Key: {private_key}\nPublic Key: {public_key}")

def get_balance():
    wallet = Tinymask(node_url)
    address = address_entry.get()
    balance = wallet.get_balance(address)
    messagebox.showinfo("Balance", f"Address: {address}\nBalance: {balance}")

def send_transaction():
    wallet = Tinymask(node_url)
    sender = sender_entry.get()
    recipient = recipient_entry.get()
    amount = amount_entry.get()
    result = wallet.send_transaction(sender, recipient, amount)
    messagebox.showinfo("Transaction Result", result)

# Create the UI
window = tk.Tk()
window.title("Tinymask Wallet")
window.geometry("400x300")

node_url = "http://localhost:5000"  # Replace with the actual node URL

# Generate Keypair
generate_keypair_button = tk.Button(window, text="Generate Keypair", command=generate_keypair)
generate_keypair_button.pack(pady=10)

# Get Balance
address_label = tk.Label(window, text="Address:")
address_label.pack()
address_entry = tk.Entry(window)
address_entry.pack()
get_balance_button = tk.Button(window, text="Get Balance", command=get_balance)
get_balance_button.pack(pady=10)

# Send Transaction
sender_label = tk.Label(window, text="Sender:")
sender_label.pack()
sender_entry = tk.Entry(window)
sender_entry.pack()

recipient_label = tk.Label(window, text="Recipient:")
recipient_label.pack()
recipient_entry = tk.Entry(window)
recipient_entry.pack()

amount_label = tk.Label(window, text="Amount:")
amount_label.pack()
amount_entry = tk.Entry(window)
amount_entry.pack()

send_transaction_button = tk.Button(window, text="Send Transaction", command=send_transaction)
send_transaction_button.pack(pady=10)

window.mainloop()
