class VM:
    def __init__(self):
        self.memory = [0] * 256
        self.registers = [0] * 8
        self.pc = 0

    def load_program(self, program):
        for addr, value in enumerate(program):
            self.memory[addr] = value

    def run(self):
        while True:
            opcode = self.memory[self.pc]
            if opcode == 0x00:  # HLT
                break
            elif opcode == 0x01:  # ADD
                reg_a = self.memory[self.pc + 1]
                reg_b = self.memory[self.pc + 2]
                self.registers[reg_a] += self.registers[reg_b]
                self.pc += 3
            elif opcode == 0x02:  # SUB
                reg_a = self.memory[self.pc + 1]
                reg_b = self.memory[self.pc + 2]
                self.registers[reg_a] -= self.registers[reg_b]
                self.pc += 3
            elif opcode == 0x03:  # MOV
                reg_a = self.memory[self.pc + 1]
                value = self.memory[self.pc + 2]
                self.registers[reg_a] = value
                self.pc += 3
            elif opcode == 0x04:  # PRINT
                reg_a = self.memory[self.pc + 1]
                print(self.registers[reg_a])
                self.pc += 2
            else:
                print(f"Invalid opcode: {opcode}")
                break


if __name__ == "__main__":
    vm = VM()
    program = [
        0x03, 0x00, 0x42,  # MOV R0, 66
        0x03, 0x01, 0x23,  # MOV R1, 35
        0x01, 0x00, 0x01,  # ADD R0, R1
        0x04, 0x00,        # PRINT R0
        0x00               # HLT
    ]
    vm.load_program(program)
    vm.run()
