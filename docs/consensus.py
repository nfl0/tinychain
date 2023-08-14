import random

# Function to simulate retrieving network usage and CPU usage percentage
def get_metrics():
    network_usage = random.uniform(0, 1)  # Simulated network usage
    cpu_usage = random.uniform(0, 100)    # Simulated CPU usage percentage
    return network_usage, cpu_usage

# Function to perform multi-party computation and select block producer
def select_block_producer(metrics_list):
    combined_metric = sum(metrics_list) / len(metrics_list)
    return metrics_list.index(min(metrics_list))

# Simulating multiple nodes participating in the consensus process
num_nodes = 5
node_metrics = []

for _ in range(num_nodes):
    network_usage, cpu_usage = get_metrics()
    combined_metric = network_usage + cpu_usage
    node_metrics.append(combined_metric)

# Select the block producer using multi-party computation
chosen_node_index = select_block_producer(node_metrics)
print(f"Chosen Node Index: {chosen_node_index}")
