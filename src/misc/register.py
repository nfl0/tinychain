import requests
import json

# Get the public key from the wallet.dat file
with open('../wallet.dat') as f:
    wallet_data = json.load(f)
    public_key = wallet_data['public_key']

# Create a POST request to the server
url = 'http://192.168.0.111:5000/register'
data = {'public_key': public_key}

# Send the request and get the response
response = requests.post(url, data=data)

# Check the response status code
if response.status_code == 200:
    # The request was successful
    print('Public key registered successfully')
else:
    # The request failed
    print('Failed to register public key')
    print(response.status_code)
    print(response.text)
