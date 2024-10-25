# TinyChain Usage Guide

## Setting Up the Development Environment

To set up the development environment for TinyChain, follow these steps:

1. **Clone the Repository**:
   ```sh
   git clone https://github.com/nfl0/tinychain.git
   cd tinychain
   ```

2. **Create a Virtual Environment**:
   ```sh
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**:
   ```sh
   pip install -r requirements.txt
   ```

4. **Run Tests**:
   ```sh
   pytest
   ```

## Running the TinyChain Node

To run the TinyChain node, follow these steps:

1. **Start the Node**:
   ```sh
   python src/tinychain.py
   ```

2. **Monitor the Logs**:
   The node will output logs to the console. You can monitor these logs to see the node's activity.

## Interacting with the TinyChain API

TinyChain provides a RESTful API for interacting with the blockchain. Here are some common API endpoints:

1. **Send a Transaction**:
   ```sh
   curl -X POST http://127.0.0.1:5000/send_transaction -H "Content-Type: application/json" -d '{
     "transaction": {
       "sender": "sender_address",
       "receiver": "receiver_address",
       "amount": 100,
       "fee": 1,
       "nonce": 0,
       "signature": "transaction_signature",
       "memo": "optional_memo"
     }
   }'
   ```

2. **Get a Block by Hash**:
   ```sh
   curl http://127.0.0.1:5000/get_block/block_hash
   ```

3. **Get a Transaction by Hash**:
   ```sh
   curl http://127.0.0.1:5000/transactions/transaction_hash
   ```

4. **Get Account Balance**:
   ```sh
   curl http://127.0.0.1:5000/get_balance/account_address
   ```

5. **Toggle Block Production**:
   ```sh
   curl -X POST http://127.0.0.1:5000/toggle_production
   ```

Replace `sender_address`, `receiver_address`, `block_hash`, `transaction_hash`, and `account_address` with the appropriate values.
