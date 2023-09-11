class VM:
    def __init__(self, memory):
        self.memory = memory
        self.registers = [0] * 8
        self.program_counter = 0
        self.accounts = {}

    def execute(self):
        while self.program_counter < len(self.memory):
            opcode = self.memory[self.program_counter]
            self.program_counter += 1

            if opcode == 1:
                # Opcode 1: Add
                reg1 = self.memory[self.program_counter]
                reg2 = self.memory[self.program_counter + 1]
                self.registers[reg1] += self.registers[reg2]
                self.program_counter += 2

            elif opcode == 2:
                # Opcode 2: Subtract
                reg1 = self.memory[self.program_counter]
                reg2 = self.memory[self.program_counter + 1]
                self.registers[reg1] -= self.registers[reg2]
                self.program_counter += 2

            elif opcode == 3:
                # Opcode 3: Multiply
                reg1 = self.memory[self.program_counter]
                reg2 = self.memory[self.program_counter + 1]
                self.registers[reg1] *= self.registers[reg2]
                self.program_counter += 2

            elif opcode == 4:
                # Opcode 4: Divide
                reg1 = self.memory[self.program_counter]
                reg2 = self.memory[self.program_counter + 1]
                if self.registers[reg2] != 0:
                    self.registers[reg1] //= self.registers[reg2]
                else:
                    print("Division by zero error.")
                self.program_counter += 2

            elif opcode == 5:
                # Opcode 5: Deposit
                reg1 = self.memory[self.program_counter]
                amount = self.registers[reg1]
                account_hex = self.memory[self.program_counter + 1]
                account_hex_str = hex(account_hex)[2:]
                if account_hex_str in self.accounts:
                    self.accounts[account_hex_str] += amount
                else:
                    self.accounts[account_hex_str] = amount
                self.program_counter += 2

            elif opcode == 6:
                # Opcode 6: Check Balance
                account_hex = self.memory[self.program_counter]
                account_hex_str = hex(account_hex)[2:]
                if account_hex_str in self.accounts:
                    self.registers[0] = self.accounts[account_hex_str]
                else:
                    self.registers[0] = 0
                self.program_counter += 1

            elif opcode == 7:
                # Opcode 7: Custom Operation
                # Add your custom operation code here
                pass  # Placeholder for your custom operation code
                self.program_counter += 1

            elif opcode == 8:
                # Opcode 8: Withdraw
                reg1 = self.memory[self.program_counter]
                amount = self.registers[reg1]
                account_hex = self.memory[self.program_counter + 1]
                account_hex_str = hex(account_hex)[2:]
                if account_hex_str in self.accounts and self.accounts[account_hex_str] >= amount:
                    self.accounts[account_hex_str] -= amount
                else:
                    print("Insufficient funds or account not found.")
                self.program_counter += 2

            elif opcode == 9:
                # Opcode 9: Transfer
                reg1 = self.memory[self.program_counter]
                reg2 = self.memory[self.program_counter + 1]
                amount = self.registers[reg1]
                source_account_hex = self.memory[self.program_counter + 2]
                destination_account_hex = self.memory[self.program_counter + 3]
                source_account_hex_str = hex(source_account_hex)[2:]
                destination_account_hex_str = hex(destination_account_hex)[2:]
                if source_account_hex_str in self.accounts and self.accounts[source_account_hex_str] >= amount:
                    if destination_account_hex_str in self.accounts:
                        self.accounts[source_account_hex_str] -= amount
                        self.accounts[destination_account_hex_str] += amount
                    else:
                        print("Destination account not found.")
                else:
                    print("Insufficient funds or source account not found.")
                self.program_counter += 4

            elif opcode == 10:
                # Opcode 10: Print Account Balances
                print("Account Balances:")
                for account_id, balance in self.accounts.items():
                    print(f"{account_id}: {balance}")
                self.program_counter += 1

            elif opcode == 99:
                # Opcode 99: Halt
                print("Halted.")
                break

    def set_register(self, reg, value):
        if value is not None:
            self.registers[reg] = value
        else:
            self.registers[reg] = 0  # Treat None as 0

def main():
    # Define the account ID once
    account_id = int("aa9cbc6fe2966cd9343aab811e38cdfea9364c6563bf4939015f700d15c629a381af89af25ea29beb073c695f155f6d22abd1c864f8339e7f3536e88c2c6b98c", 16)

    memory = [
        5,  # Deposit
        0,  # Register 0 (amount)
        account_id,
        6,  # Check Balance
        account_id,
        8,  # Withdraw
        0,  # Register 0 (amount)
        account_id,
        10,  # Print Account Balances
        99,  # Halt
    ]

    vm = VM(memory)

    vm.set_register(0, 232)  # Set Register 0 to the initial deposit amount

    vm.execute()

    print("Balance in Account:", vm.registers[0])

if __name__ == "__main__":
    main()