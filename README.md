this is tinychain
tinychain is this

## Setting up a Python Virtual Environment

0. Create a virtual environment in root dir of project:
   ```bash
   python -m venv .venv
   ```

1. Activate the virtual environment:
   - On Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - On macOS and Linux:
     ```bash
     source .venv/bin/activate
     ```

2. Install the required dependencies using `pip`:
   ```bash
   pip install -r requirements.txt
   ```

## Setting up and Running Docker Containers

1. Build and start the Docker containers:
   ```bash
   docker-compose up --build -d
   ```

2. Configure the `PEER_URIS` for each node:
   ```bash
   ./scripts/configure_peers.sh
   ```

3. Use the `manage_nodes.sh` script to start, stop, and reset the containers:
   - Start the containers:
     ```bash
     ./scripts/manage_nodes.sh start
     ```
   - Stop the containers:
     ```bash
     ./scripts/manage_nodes.sh stop
     ```
   - Reset the containers:
     ```bash
     ./scripts/manage_nodes.sh reset
     ```

4. Use the `manage_nodes.sh` script to start and stop the `tinychain.py` script in a specific container:
   - Start the `tinychain.py` script:
     ```bash
     ./scripts/manage_nodes.sh start-tinychain <container_name>
     ```
   - Stop the `tinychain.py` script:
     ```bash
     ./scripts/manage_nodes.sh stop-tinychain <container_name>
     ```
