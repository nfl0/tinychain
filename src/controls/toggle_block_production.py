import requests

def toggle_block_production():
    url = "http://127.0.0.1:5000/toggle_production"
    response = requests.post(url)
    if response.status_code == 200:
        print("Block production toggled successfully.")
    else:
        print("Failed to toggle block production.")

if __name__ == "__main__":
    toggle_block_production()
