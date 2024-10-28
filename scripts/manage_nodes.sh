#!/bin/bash

# Function to start the containers
start_containers() {
    docker-compose up -d
}

# Function to stop the containers
stop_containers() {
    docker-compose down
}

# Function to reset the containers
reset_containers() {
    docker-compose down -v
    docker-compose up -d
}

# Function to start the tinychain.py script in a container
start_tinychain() {
    container_name=$1
    docker exec -d $container_name python /app/src/tinychain.py
}

# Function to stop the tinychain.py script in a container
stop_tinychain() {
    container_name=$1
    docker exec -d $container_name pkill -f tinychain.py
}

# Main script logic
case "$1" in
    start)
        start_containers
        ;;
    stop)
        stop_containers
        ;;
    reset)
        reset_containers
        ;;
    start-tinychain)
        if [ -z "$2" ]; then
            echo "Please provide the container name."
            exit 1
        fi
        start_tinychain $2
        ;;
    stop-tinychain)
        if [ -z "$2" ]; then
            echo "Please provide the container name."
            exit 1
        fi
        stop_tinychain $2
        ;;
    *)
        echo "Usage: $0 {start|stop|reset|start-tinychain|stop-tinychain} [container_name]"
        exit 1
        ;;
esac
