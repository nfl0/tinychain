import random
import syft

# Simulated encrypted data sharing
def share_data(data, participants):
    encrypted_data = {}
    for participant in participants:
        encrypted_data[participant] = participant.encrypt(data)
    return encrypted_data

# Simulated encrypted computation
def compute_sum(encrypted_data):
    sum_encrypted = encrypted_data[0]
    for data in encrypted_data[1:]:
        sum_encrypted += data
    return sum_encrypted

# Simulated decryption
def decrypt_result(encrypted_result, participant):
    return participant.decrypt(encrypted_result)

# Simulating participants
num_participants = 5
participants = [syft.VirtualMachine(name=f"Participant {i}") for i in range(num_participants)]

# Simulating encrypted data sharing and computation
node_metrics = [random.uniform(0, 1) for _ in range(num_participants)]
encrypted_metrics = share_data(node_metrics, participants)
encrypted_sum = compute_sum(encrypted_metrics)

# Simulating decryption and revealing the result
chosen_node_index = decrypt_result(encrypted_sum, participants[0])
print(f"Chosen Node Index: {chosen_node_index}")
