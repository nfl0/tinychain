@app.route('/get_block/<string:block_hash>', methods=['GET'])
def get_block_by_hash(block_hash):
    block_data = storage_engine.fetch_block(block_hash)
    if block_data is not None:
        return jsonify(block_data)
    return jsonify({'error': 'Block not found'}), 404

@app.route('/get_balance/<string:account_address>', methods=['GET'])
def get_balance(account_address):
    balance = storage_engine.fetch_balance(account_address)
    if balance is not None:
        return jsonify({'balance': balance})
    return jsonify({'error': 'Account not found'}), 404

@app.route('/get_accounts', methods=['GET'])
def get_accounts():
    accounts = []
    for key, value in storage_engine.db_accounts:
        account = {
            'address': key.decode(),
            'balance': int(value.decode())
        }
        accounts.append(account)
    return jsonify(accounts)