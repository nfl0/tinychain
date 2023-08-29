class Mempool:
    def __init__(self):
        self.transactions = Queue()
    def add_transaction(self, transaction):
        self.transactions.put(transaction)
    def get_transaction(self):
        return self.transactions.get()
    def is_empty(self):
        return self.transactions.empty()