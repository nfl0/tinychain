class StakingVM:
    def __init__(self):
        self.stack = []
        self.memory = {}
        self.contract_states = {}
        self.account_balances = {}
        self.log = []

    def execute(self, bytecode):
        pc = 0  # Program Counter
        while pc < len(bytecode):
            opcode = bytecode[pc]
            if opcode == "PUSH":
                pc += 1
                value = bytecode[pc]
                self.stack.append(value)
            elif opcode == "POP":
                self.stack.pop()
            elif opcode == "LOAD_CONTRACT_STATE":
                pc += 1
                contract_address = bytecode[pc]
                self.stack.append(self.contract_states.get(contract_address, {}))
            elif opcode == "STORE_CONTRACT_STATE":
                pc += 1
                contract_address = bytecode[pc]
                state = self.stack.pop()
                self.contract_states[contract_address] = state
            elif opcode == "LOAD_ACCOUNT_BALANCE":
                pc += 1
                account_address = bytecode[pc]
                self.stack.append(self.account_balances.get(account_address, 0))
            elif opcode == "STORE_ACCOUNT_BALANCE":
                pc += 1
                account_address = bytecode[pc]
                balance = self.stack.pop()
                self.account_balances[account_address] = balance
            elif opcode == "LOG":
                message = self.stack.pop()
                self.log.append(message)
            elif opcode == "ADD":
                a = self.stack.pop()
                b = self.stack.pop()
                result = a + b
                self.stack.append(result)
            elif opcode == "SUB":
                a = self.stack.pop()
                b = self.stack.pop()
                result = a - b
                self.stack.append(result)
            elif opcode == "EQ":
                a = self.stack.pop()
                b = self.stack.pop()
                result = a == b
                self.stack.append(result)
            elif opcode == "JUMP_IF_FALSE":
                pc += 1
                target = bytecode[pc]
                condition = self.stack.pop()
                if not condition:
                    pc = target
            elif opcode == "JUMP":
                pc += 1
                target = bytecode[pc]
                pc = target
            else:
                raise Exception(f"Invalid opcode: {opcode}")
            pc += 1

    def execute_staking_contract(self, bytecode):
        self.execute(bytecode)

    def get_logs(self):
        return self.log


# Example usage of the StakingVM
vm = StakingVM()

# Define the bytecode for the staking contract
# Define the bytecode for the staking contract
staking_contract_bytecode = [
    "LOAD_CONTRACT_STATE", "staking_contract",  # Load staking state
    "PUSH", "account_address",  # Load account address
    "LOAD_ACCOUNT_BALANCE",  # Load staked balance
    "PUSH", "amount",  # Load the staking amount
    "ADD",  # Add the amount to the balance
    "STORE_ACCOUNT_BALANCE",  # Store the updated balance
    "PUSH", "Staked {amount} tokens.",  # Log the staking event
    "LOG",
]


# Initialize contract state and account balances
vm.contract_states["staking_contract"] = {}
vm.account_balances["account_address"] = 0

# Set input values
vm.memory["account_address"] = "alice"
vm.memory["amount"] = 100

# Execute the staking contract
vm.execute_staking_contract(staking_contract_bytecode)

# Get logs
logs = vm.get_logs()
for log in logs:
    print(log)
