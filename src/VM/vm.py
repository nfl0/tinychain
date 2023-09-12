class VM6503:
    def __init__(self):
        self.memory = bytearray(256)  # 256 bytes of memory
        self.memory_pointer = 0
        self.stack = []
        self.storage = {}
        self.pc = 0
        self.halted = False

    def load_bytecode(self, bytecode):
        if len(bytecode) <= len(self.memory):
            self.memory[:len(bytecode)] = bytecode
        else:
            raise ValueError("Bytecode too large for memory")

    def execute_opcode(self, opcode):
        if opcode == 0x00:  # Halt
            self.halted = True
        elif opcode == 0x01:  # ADD
            b = self.stack.pop()
            a = self.stack.pop()
            result = a + b
            self.stack.append(result)
        elif opcode == 0x02:  # SUB
            b = self.stack.pop()
            a = self.stack.pop()
            result = a - b
            self.stack.append(result)
        elif opcode == 0x03:  # PUSH
            value = self.memory[self.pc]
            self.pc += 1
            self.stack.append(value)
        elif opcode == 0x04:  # POP
            value = self.stack.pop()
            self.memory[self.memory_pointer] = value
            self.memory_pointer += 1
        elif opcode == 0x05:  # SWAP
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append(a)
            self.stack.append(b)
        elif opcode == 0x06:  # SSTORE
            key = self.stack.pop()
            value = self.stack.pop()
            self.storage[key] = value
        elif opcode == 0x07:  # SLOAD
            key = self.stack.pop()
            if key in self.storage:
                self.stack.append(self.storage[key])
            else:
                self.stack.append(0)
        elif opcode == 0x0A:  # JUMPIF
            condition = self.stack.pop()
            jump_destination = self.stack.pop()
            if condition != 0:
                self.pc = jump_destination

        # Add more opcodes as needed
        else:
            raise ValueError(f"Invalid opcode: {opcode}")

    def run(self):
        while not self.halted:
            opcode = self.memory[self.pc]
            self.pc += 1
            self.execute_opcode(opcode)
