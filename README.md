# TinyChain

TinyChain is a lightweight and efficient blockchain solution. This document provides instructions for setting up and running TinyChain.

## Setting up a Python Virtual Environment

1. Create a virtual environment in the root directory of the project:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - On Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - On macOS and Linux:
     ```bash
     source .venv/bin/activate
     ```

3. Install the required dependencies using `pip`:
   ```bash
   pip install -r requirements.txt
   ```

## Running TinyChain

1. Ensure that you have a wallet generated. If not, run the wallet generator script:
   ```bash
   python src/wallet_generator.py
   ```

2. Start the TinyChain node:
   ```bash
   python src/tinychain.py
   ```

3. You can interact with the TinyChain node using the provided API. For example, to send a transaction, you can use the `tinymask` script:
   ```bash
   python src/tinymask/tinymask.py
   ```

## Additional Information

For more details on the architecture and components of TinyChain, refer to the `docs/architecture.md` file.
