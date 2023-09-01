import blake3

class Transaction:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.message = f"{self.sender}-{self.receiver}-{self.amount}"
        self.transaction_hash = self.generate_transaction_hash()
        self.memo = kwargs.get('memo', '')

    def generate_transaction_hash(self):
        values = [str(self.sender), str(self.receiver), str(self.amount), str(self.signature)]
        return blake3.blake3(''.join(values).encode()).hexdigest()

    def to_dict(self):
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'signature': self.signature,
            'memo': self.memo,
        }
