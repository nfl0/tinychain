# Inside the Miner class __init__ method
self.previous_block_hash = last_block_data['block_hash'] if last_block_data else None
self.block_height = last_block_data['height'] + 1 if last_block_data else 0
