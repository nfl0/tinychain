from flask import Flask, request, jsonify
import threading
import time
import random

app = Flask(__name__)

class Mempool:
    def __init__(self):
        self.transactions = []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)

mempool = Mempool()

class Miner(threading.Thread):
    def __init__(self, mempool):
        super().__init__()
        self.mempool = mempool
        self.blockchain = []  # A simple list to represent the blockchain
        self.running = True
    
    def run(self):
        while self.running:
            if self.mempool.transactions:
                random_transaction = random.choice(self.mempool.transactions)
                self.mempool.transactions.remove(random_transaction)
                self.blockchain.append(random_transaction)
                print(f"Added transaction '{random_transaction}' to a new block.")
            time.sleep(5)  # Wait for 5 seconds

miner = Miner(mempool)

@app.route('/sendTransaction', methods=['POST'])
def send_transaction():
    data = request.json
    if 'transaction' in data:
        transaction = data['transaction']
        mempool.add_transaction(transaction)
        return jsonify({'message': 'Transaction added to mempool'})
    else:
        return jsonify({'error': 'Transaction data not provided'})

@app.route('/getBlockchain', methods=['GET'])
def get_blockchain():
    return jsonify(miner.blockchain)

if __name__ == '__main__':
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.start()
    
    # Start the miner thread
    miner.start()
    
    try:
        while True:
            pass  # Keep the main thread running
    except KeyboardInterrupt:
        miner.running = False
        miner.join()  # Wait for the miner thread to finish
        flask_thread.join()  # Wait for the Flask thread to finish
