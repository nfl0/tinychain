import asyncio
import websockets
import json

async def receive_updates():
    uri = "ws://localhost:5001/wss"  # Replace with your node's IP and port

    async with websockets.connect(uri) as websocket:
        # Send a "Hello, World!" message when the connection is established
        await websocket.send("Hello, World!")

        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if 'transaction_hash' in data:
                # Handle incoming transaction data
                print("Received Transaction:")
                print(json.dumps(data, indent=4))
            elif 'block_hash' in data:
                # Handle incoming block data
                print("Received Block:")
                print(json.dumps(data, indent=4))
            else:
                # Handle other types of data if needed
                print("Received Data:")
                print(json.dumps(data, indent=4))

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(receive_updates())
