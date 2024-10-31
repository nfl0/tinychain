from transaction import Transaction
from forger import Forger

TINYCOIN = 1000000000000000000

def genesis_procedure(transactionpool, forger):
    genesis_addresses = [
        "7ff08d4ddd1be1305e77db4064bb71f2c0872599334db03fc36d8cab3fb349c4e1dfb6262bd3e118f37aa8d19827f0aa56bf9052bb9c5b6e16e0679706124e38",
        "336bf5193983cb2c287f7695343730ccf5f0a88da961459e996b1d4cc07480f1649a682e1194db36bd9957e6cb6cfb4c2185306f31da9723bc84b03e4116ce57",
        "448769135d4bef3c2b88f81829dc73433fd05882082bb67c4962ba9ef2acf6967083d7f142758150f6f01a87e7a18aa568400b5a05b2b24ccce415d764fed636",
        "f0689410ce583320822fb2761600b1786860711ec751fae27d2341ea1befbcc0a3c1afde193e9d2d5d9a9f5a79c7f18efa49e4f5905767c4d518b9c78850305f",
        "ce8958afa7c8ac763308705cda306d21119f5401d08d249b1cdcbd6306faba91c6f31a210c7827a494891d17d357dfa755a6e4ae5dd09ffa3803fbafe58c027c",
        "de280016480735a12e975d4c869808bdee564d544e762020446462261d704d8d4a8cab311c6447e3299108b7317db9d5316057c0c0cf7379dda2cd12c20d7660"
    ]
    staking_contract_address = "7374616b696e67"
    genesis_transactions = [
        Transaction("genesis", genesis_addresses[0], 10000*TINYCOIN, 120, 0, "consensus", ""),
        Transaction(genesis_addresses[0], staking_contract_address, 1000*TINYCOIN, 110, 0, "genesis_signature_0", "stake"),
        Transaction("genesis", genesis_addresses[1], 10000*TINYCOIN, 100, 1, "consensus", ""),
        Transaction(genesis_addresses[1], staking_contract_address, 1000*TINYCOIN, 90, 0, "genesis_signature_1", "stake"),
        Transaction("genesis", genesis_addresses[2], 10000*TINYCOIN, 80, 2, "consensus", ""),
        Transaction(genesis_addresses[2], staking_contract_address, 1000*TINYCOIN, 70, 0, "genesis_signature_2", "stake"),
        Transaction("genesis", genesis_addresses[3], 10000*TINYCOIN, 60, 3, "consensus", ""),
        Transaction(genesis_addresses[3], staking_contract_address, 1000*TINYCOIN, 50, 0, "genesis_signature_3", "stake"),
        Transaction("genesis", genesis_addresses[4], 10000*TINYCOIN, 40, 4, "consensus", ""),
        Transaction(genesis_addresses[4], staking_contract_address, 1000*TINYCOIN, 30, 0, "genesis_signature_4", "stake"),
        Transaction("genesis", genesis_addresses[5], 10000*TINYCOIN, 20, 5, "consensus", ""),
        Transaction(genesis_addresses[5], staking_contract_address, 1000*TINYCOIN, 10, 0, "genesis_signature_5", "stake")
    ]
    for transaction in genesis_transactions:
        transactionpool.add_transaction(transaction)
    forger.forge_new_block(False, None, True)
