import asyncio
import random
import aiohttp
import websockets

# Simulated mempools for two blockchain nodes
mempool_node1 = []
mempool_node2 = []

# Function to simulate adding a transaction to a mempool
async def add_transaction_to_mempool(node, transaction):
    await asyncio.sleep(random.uniform(0.1, 1))  # Simulate random delay
    node.append(transaction)
    print(f"Added transaction to Node {node}: {transaction}")

# Function to simulate removing a random transaction from a mempool
async def remove_random_transaction_from_mempool(node):
    await asyncio.sleep(random.uniform(0.1, 1))  # Simulate random delay
    if node:
        removed_transaction = node.pop(random.randint(0, len(node) - 1))
        print(f"Removed transaction from Node {node}: {removed_transaction}")

# Function to handle incoming WebSocket messages
async def handle_message(message, websocket):
    if message == "sync":
        # Send the local mempool to the other node
        if websocket == node1_ws:
            await node2_ws.send(str(mempool_node1))
        else:
            await node1_ws.send(str(mempool_node2))
    elif message.startswith("add"):
        # Add a transaction to the local mempool
        transaction = message.split(" ", 1)[1]
        await add_transaction_to_mempool(
            mempool_node1 if websocket == node1_ws else mempool_node2, transaction
        )
    elif message.startswith("remove"):
        # Remove a random transaction from the local mempool
        await remove_random_transaction_from_mempool(
            mempool_node1 if websocket == node1_ws else mempool_node2
        )

# WebSocket server for Node 1
async def node1_handler(websocket, path):
    global node1_ws
    node1_ws = websocket
    await websocket.send("Connected to Node 1")

    async for message in websocket:
        await handle_message(message, websocket)

# WebSocket server for Node 2
async def node2_handler(websocket, path):
    global node2_ws
    node2_ws = websocket
    await websocket.send("Connected to Node 2")

    async for message in websocket:
        await handle_message(message, websocket)

# Start the WebSocket servers
start_server1 = websockets.serve(node1_handler, "localhost", 8765)
start_server2 = websockets.serve(node2_handler, "localhost", 8766)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_server1)
    asyncio.get_event_loop().run_until_complete(start_server2)
    asyncio.get_event_loop().run_forever()
