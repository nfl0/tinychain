#!/bin/bash

# Build the Docker images
docker-compose build

# Start the containers
docker-compose up -d

# Initialize the wallets and set up the initial state for each node
for i in {1..6}; do
    docker exec -it node$i python src/wallet_generator.py
done
