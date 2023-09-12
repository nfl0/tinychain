from vm import VM6503


def main():
    vm = VM6503()

    # Load the bytecode
    bytecode = [
        0x01,  # ADD
        0x02,  # SUB
        0x03,  # PUSH
        0x04,  # POP
        0x05,  # SWAP
        0x06,  # SSTORE
        0x07,  # SLOAD
        0x0A,  # JUMPIF
    ]
    vm.load_bytecode(bytecode)

    # Run the program
    vm.run()


if __name__ == "__main__":
    main()
