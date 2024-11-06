import requests
import logging
from block import BlockHeader, Signature
from wallet import Wallet
from parameters import PEER_DISCOVERY_METHOD, PEER_DISCOVERY_FILE, PEER_DISCOVERY_API

def get_peers():
    if PEER_DISCOVERY_METHOD == 'file':
        try:
            with open(PEER_DISCOVERY_FILE, 'r') as file:
                peers = file.read().splitlines()
                return peers
        except Exception as e:
            logging.error(f"Error reading peers from file: {e}")
            return []
    elif PEER_DISCOVERY_METHOD == 'api':
        try:
            response = requests.get(PEER_DISCOVERY_API, timeout=0.3)
            if response.status_code == 200:
                peers = response.json().get('peers', [])
                return peers
            else:
                logging.error(f"Failed to fetch peers from API: {response.status_code}")
                return []
        except Exception as e:
            logging.error(f"Error fetching peers from API: {e}")
            return []
    else:
        logging.error(f"Unknown peer discovery method: {PEER_DISCOVERY_METHOD}")
        return []

def broadcast_block_header(block_header):
    logging.info(f"Broadcasting block header with hash: {block_header.block_hash}")
    peers = get_peers()
    for peer_uri in peers:
        try:
            response = requests.post(f'http://{peer_uri}/receive_block', json={'block_header': block_header.to_dict()}, timeout=0.3)
            if response.status_code == 200:
                logging.info(f"Block header broadcasted to peer {peer_uri}")
            else:
                logging.error(f"Failed to broadcast block header to peer {peer_uri}")
        except Exception as e:
            logging.error(f"Error broadcasting block header to peer {peer_uri}: {e}")

def receive_block_header(request):
    logging.info("Received block header")
    data = request.json()
    block_header_data = data.get('block_header')
    if not block_header_data:
        logging.error("Invalid block header data received")
        return {'error': 'Invalid block header data'}, 400

    block_header = BlockHeader.from_dict(block_header_data)

    # Verify the validity of the block header
    if not validation_engine.validate_block_header(block_header, storage_engine.fetch_last_block_header()):
        logging.error("Invalid block header received")
        return {'error': 'Invalid block header'}, 400

    # Verify the identity of the proposer through the included signature
    proposer_signature = find_proposer_signature(block_header)
    if proposer_signature is None or not Wallet.verify_signature(block_header.block_hash, proposer_signature.signature_data, proposer_signature.validator_address):
        logging.error("Invalid proposer signature received")
        return {'error': 'Invalid proposer signature'}, 400

    # Check if a block header with the same hash already exists in memory
    if block_header.block_hash in forger.in_memory_block_headers:
        existing_block_header = forger.in_memory_block_headers[block_header.block_hash]
        existing_block_header.append_signatures(block_header.signatures)
        logging.info(f"Appended signatures to existing block header with hash: {block_header.block_hash}")
    else:
        # Submit the received block header to the forger for replay
        forger.replay_block(block_header)
        logging.info(f"Submitted block header with hash: {block_header.block_hash} for replay")

    return {'message': 'Block header received and processed'}, 200

def broadcast_transaction(transaction, sender_uri):
    peers = get_peers()
    for peer_uri in peers:
        if peer_uri != sender_uri:
            try:
                response = requests.post(f'http://{peer_uri}/send_transaction', json={'transaction': transaction.to_dict()}, timeout=0.3)
                if response.status_code == 200:
                    logging.info(f"Transaction broadcasted to peer {peer_uri}")
                else:
                    logging.error(f"Failed to broadcast transaction to peer {peer_uri}")
            except Exception as e:
                logging.error(f"Error broadcasting transaction to peer {peer_uri}: {e}")
