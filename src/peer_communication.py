import requests
import logging
from block import BlockHeader, Signature
from wallet import Wallet
from parameters import PEER_URIS

def broadcast_block_header(block_header):
    for peer_uri in PEER_URIS:
        try:
            response = requests.post(f'http://{peer_uri}/receive_block', json={'block_header': block_header.to_dict()})
            if response.status_code == 200:
                logging.info(f"Block header broadcasted to peer {peer_uri}")
            else:
                logging.error(f"Failed to broadcast block header to peer {peer_uri}")
        except Exception as e:
            logging.error(f"Error broadcasting block header to peer {peer_uri}: {e}")

def receive_block_header(request):
    data = request.json()
    block_header_data = data.get('block_header')
    if not block_header_data:
        return {'error': 'Invalid block header data'}, 400

    block_header = BlockHeader.from_dict(block_header_data)

    # Verify the validity of the block header
    if not validation_engine.validate_block_header(block_header, storage_engine.fetch_last_block_header()):
        return {'error': 'Invalid block header'}, 400

    # Verify the identity of the proposer through the included signature
    proposer_signature = find_proposer_signature(block_header)
    if proposer_signature is None or not Wallet.verify_signature(block_header.block_hash, proposer_signature.signature_data, proposer_signature.validator_address):
        return {'error': 'Invalid proposer signature'}, 400

    # Check if a block header with the same hash already exists in memory
    if block_header.block_hash in forger.in_memory_block_headers:
        existing_block_header = forger.in_memory_block_headers[block_header.block_hash]
        existing_block_header.append_signatures(block_header.signatures)
    else:
        # Submit the received block header to the forger for replay
        forger.forge_new_block(replay=True, block_header=block_header)

    return {'message': 'Block header received and processed'}, 200

def broadcast_transaction(transaction, sender_uri):
    for peer_uri in PEER_URIS:
        if peer_uri != sender_uri:
            try:
                response = requests.post(f'http://{peer_uri}/send_transaction', json={'transaction': transaction.to_dict()})
                if response.status_code == 200:
                    logging.info(f"Transaction broadcasted to peer {peer_uri}")
                else:
                    logging.error(f"Failed to broadcast transaction to peer {peer_uri}")
            except Exception as e:
                logging.error(f"Error broadcasting transaction to peer {peer_uri}: {e}")
