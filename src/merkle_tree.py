import blake3

class MerkleTree:
    def __init__(self):
        self.leaves = []

    def append(self, data):
        hasher = blake3.blake3()
        hasher.update(data)
        self.leaves.append(hasher.digest())

    def root_hash(self):
        if not self.leaves:
            return b''

        leaves = self.leaves[:]
        while len(leaves) > 1:
            new_leaves = []
            for i in range(0, len(leaves), 2):
                left_hash = leaves[i]
                right_hash = leaves[i + 1] if i + 1 < len(leaves) else leaves[i]
                combined_hash = blake3.blake3(left_hash + right_hash).digest()
                new_leaves.append(combined_hash)
            leaves = new_leaves

        return leaves[0]
