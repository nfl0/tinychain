from aiohttp import web
import aiohttp_jinja2
import jinja2
import requests

app = web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('src/templates'))

@aiohttp_jinja2.template('index.html')
async def index(request):
    return {}

async def fetch_blocks(request):
    response = requests.get('http://127.0.0.1:5000/get_block_by_height')
    blocks = response.json()
    return web.json_response(blocks)

async def fetch_transactions(request):
    response = requests.get('http://127.0.0.1:5000/transactions')
    transactions = response.json()
    return web.json_response(transactions)

async def fetch_account_balance(request):
    account_address = request.match_info['account_address']
    response = requests.get(f'http://127.0.0.1:5000/get_balance/{account_address}')
    balance = response.json()
    return web.json_response(balance)

app.router.add_get('/', index)
app.router.add_get('/blocks', fetch_blocks)
app.router.add_get('/transactions', fetch_transactions)
app.router.add_get('/balance/{account_address}', fetch_account_balance)

if __name__ == '__main__':
    web.run_app(app, port=8080)
