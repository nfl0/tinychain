#!/bin/bash

# Function to get the IP address of a container
get_container_ip() {
    docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $1
}

# Get the IP addresses of the running containers
node1_ip=$(get_container_ip node1)
node2_ip=$(get_container_ip node2)
node3_ip=$(get_container_ip node3)
node4_ip=$(get_container_ip node4)
node5_ip=$(get_container_ip node5)
node6_ip=$(get_container_ip node6)

# Create the PEER_URIS array
peer_uris=("http://$node1_ip:5000" "http://$node2_ip:5000" "http://$node3_ip:5000" "http://$node4_ip:5000" "http://$node5_ip:5000" "http://$node6_ip:5000")

# Update the PEER_URIS array in parameters.py
update_peer_uris() {
    sed -i "s|PEER_URIS = \[.*\]|PEER_URIS = [${peer_uris[*]}]|" src/parameters.py
}

# Call the function to update PEER_URIS
update_peer_uris
