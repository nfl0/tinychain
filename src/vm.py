import logging
from parameters import BLOCK_REWARD
from merkle_tree import MerkleTree

tinycoin = 1000000000000000000  # 1 tinycoin = 1000000000000000000 tatoshi
BLOCK_REWARD = BLOCK_REWARD * tinycoin

class TinyVMEngine:
    def __init__(self, current_state):
        self.merkle_tree = MerkleTree()
        self.current_state = current_state

        ### System Contracts ###
        self.accounts_contract_address = "6163636f756e7473"
        self.staking_contract_address = "7374616b696e67"  # 'staking' in hex
        self.storage_contract_address = "73746f72616765"  # 'storage' in hex

    def exec(self, transactions, proposer):
        accounts_contract_state = self.current_state.get(self.accounts_contract_address, {})
        staking_contract_state = self.current_state.get(self.staking_contract_address, {})

        summary = {"success": 0, "failed": 0}

        # Reward proposer (if not genesis block)
        if proposer != "genesis":
            accounts_contract_state = self.execute_accounts_contract(
                accounts_contract_state, proposer, None, BLOCK_REWARD, "credit"
            )

        # Process each transaction
        for transaction in transactions:
            sender, receiver, amount, memo = (
                transaction.sender,
                transaction.receiver,
                transaction.amount,
                transaction.memo,
            )

            success = self.process_transaction(
                accounts_contract_state, staking_contract_state, sender, receiver, amount, memo
            )
            if success:
                summary["success"] += 1
            else:
                summary["failed"] += 1

        # Final state update
        state = {
            self.accounts_contract_address: accounts_contract_state,
            self.staking_contract_address: staking_contract_state,
        }

        # Calculate the Merkle root
        state_root = self.merkle_tree.root_hash().hex()

        # Log summary result
        logging.info(f"TinyVM: Execution Summary - Success: {summary['success']}, Failed: {summary['failed']}")
        logging.info(f"TinyVM: State after execution: {state}")

        return state_root, state

    def process_transaction(self, accounts_state, staking_state, sender, receiver, amount, memo):
        """Handles a single transaction and returns True on success, False on failure."""
        if receiver == self.staking_contract_address and memo in ("stake", "unstake"):
            is_stake = memo == "stake"
            staking_state, accounts_state = self.execute_staking_contract(
                staking_state, sender, amount, is_stake, accounts_state
            )
            return True
        elif memo not in ("stake", "unstake") and receiver == self.staking_contract_address:
            logging.info(f"TinyVM: Invalid memo '{memo}'. Use 'stake' or 'unstake'.")
            return False

        # Execute regular transfer
        return self.execute_accounts_contract(accounts_state, sender, receiver, amount, "transfer") is not None

    def execute_accounts_contract(self, contract_state, sender, receiver, amount, operation):
        if contract_state is None:
            contract_state = {sender: 6000 * tinycoin}  # Genesis account initial balance

        if operation == "credit":
            contract_state[sender] = contract_state.get(sender, 0) + amount
        elif operation == "transfer":
            sender_balance = contract_state.get(sender, 0)
            receiver_balance = contract_state.get(receiver, 0)

            if sender_balance >= amount:
                contract_state[sender] = sender_balance - amount
                contract_state[receiver] = receiver_balance + amount
            else:
                logging.info(f"TinyVM: Insufficient balance for sender: {sender}")
                return None  # Transaction failed

        self.merkle_tree.append(bytes(str(contract_state), "utf-8"))
        return contract_state

    def execute_staking_contract(self, contract_state, sender, amount, is_stake, accounts_state):
        if contract_state is None:
            contract_state = {}

        staked_balance = contract_state.get(sender, {"balance": 0, "status": "active", "index": len(contract_state)})

        if is_stake:
            staked_balance["balance"] += amount
            staked_balance["status"] = "active"
        else:
            if staked_balance["balance"] > 0:
                released_balance = staked_balance["balance"]
                staked_balance["balance"] = 0
                staked_balance["status"] = "inactive"

                self.execute_accounts_contract(
                    accounts_state, self.staking_contract_address, sender, released_balance, "transfer"
                )
            else:
                logging.info(f"TinyVM: No staked tinycoins to unstake for {sender}.")
                return contract_state, accounts_state  # No change

        contract_state[sender] = staked_balance
        self.merkle_tree.append(bytes(str(contract_state), "utf-8"))
        return contract_state, accounts_state
