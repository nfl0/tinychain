import asyncio
import random
from aiohttp import web, WSMsgType

app = web.Application()
mempool = set()

async def mempool_sync(websocket, path):
    global mempool

    while True:
        try:
            await asyncio.sleep(random.uniform(3, 5))
            tx = f'DumbTransaction-{random.randint(101, 200)}'
            mempool.add(tx)

            # Send updated mempool to the other node
            await websocket.send(f'MempoolUpdate: {tx}')

            # Receive mempool updates from the other node
            async for msg in websocket:
                if msg.type == WSMsgType.TEXT:
                    if msg.data.startswith('MempoolUpdate: '):
                        tx = msg.data.split(': ')[1]
                        mempool.add(tx)
                        print(f'Node2: Received Mempool Update: {tx}')
        except asyncio.CancelledError:
            break

app.router.add_get('/ws', mempool_sync)

if __name__ == '__main__':
    web.run_app(app, port=8081)
