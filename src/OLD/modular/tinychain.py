#from app import app
from storage_engine import StorageEngine
from validation_engine import ValidationEngine
from mempool import Mempool
from miner import Miner
import threading
import logging
import atexit
from flask import Flask, request, jsonify

BLOCK_TIME = 5
BLOCK_REWARD = 10
miner_public_key = 'aa9cbc6fe2966cd9343aab811e38cdfea9364c6563bf4939015f700d15c629a381af89af25ea29beb073c695f155f6d22abd1c864f8339e7f3536e88c2c6b98c'


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create instances of components
storage_engine = StorageEngine(BLOCK_REWARD)
validation_engine = ValidationEngine(storage_engine)
mempool = Mempool()
last_block_data = storage_engine.fetch_last_block()
miner = Miner(mempool, storage_engine, validation_engine, miner_public_key, last_block_data, BLOCK_TIME)

app = Flask(__name__)

# API endpoints
@app.route('/send_transaction', methods=['POST'])
def send_transaction():
    data = request.json
    if 'transaction' in data and validation_engine.validate_transaction(data['transaction']):
        transaction = data['transaction']
        try:
            transaction['amount'] = int(transaction['amount'])
        except ValueError:
            return jsonify({'error': 'Invalid transaction amount'}), 400
        transaction['message'] = f"{transaction['sender']}-{transaction['receiver']}-{transaction['amount']}"
        
        # Add the transaction to the mempool (replacing existing if any)
        mempool.add_transaction(transaction)
        
        return jsonify({'message': 'Transaction added to mempool'})
    return jsonify({'error': 'Invalid transaction data'}), 400


@app.route('/get_block/<string:block_hash>', methods=['GET'])
def get_block_by_hash(block_hash):
    block_data = storage_engine.fetch_block(block_hash)
    if block_data is not None:
        return jsonify(block_data)
    return jsonify({'error': 'Block not found'}), 404

stop_event = threading.Event()
def cleanup():
    stop_event.set()
    miner.join()
    flask_thread.join()
    storage_engine.close()
atexit.register(cleanup)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.start()

    miner.start()

    stop_event.wait()