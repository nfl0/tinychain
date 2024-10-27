# TinyChain Architecture

## Overview

TinyChain is a blockchain project designed to provide a lightweight and efficient blockchain solution. The architecture of TinyChain is modular and consists of several key components that work together to achieve consensus, validate transactions, and maintain the blockchain state.

## Main Components

### 1. Node
The TinyChain node is responsible for maintaining the blockchain, validating transactions, and participating in the consensus process. It consists of several sub-components:

- **Transaction Pool**: A pool that holds pending transactions before they are included in a block.
- **Forger**: Responsible for creating new blocks and adding them to the blockchain.
- **Storage Engine**: Manages the storage of blocks, transactions, and state data.
- **Validation Engine**: Validates transactions and blocks to ensure they adhere to the protocol rules.
- **TinyVM Engine**: Executes smart contracts and updates the blockchain state.

### 2. Wallet
The wallet is responsible for generating key pairs, signing transactions, and verifying signatures. It provides a user-friendly interface for interacting with the blockchain.

### 3. API
The API provides endpoints for interacting with the TinyChain node. It allows users to send transactions, query the blockchain state, and interact with smart contracts.

## Component Interactions

1. **Transaction Flow**:
   - Users create transactions using their wallets and send them to the TinyChain node via the API.
   - The node validates the transactions and adds them to the transaction pool.
   - The forger selects transactions from the pool, creates a new block, and broadcasts it to the network.
   - Other nodes validate the block and add it to their local blockchain.

2. **Block Creation**:
   - The forger collects transactions from the transaction pool and validates them.
   - The TinyVM Engine executes the transactions and updates the state.
   - The forger creates a new block with the updated state and broadcasts it to the network.

3. **Consensus**:
   - TinyChain uses a round-robin consensus mechanism where validators take turns producing blocks.
   - Validators sign the block and broadcast their signatures to the network.
   - Once a block receives signatures from a majority of validators, it is considered valid and added to the blockchain.

## Staking Contract

The staking contract in TinyChain includes the following fields for each validator:

- **Public Key**: The public key of the validator.
- **Staked Balance**: The amount of tokens staked by the validator.
- **Status**: The status of the validator (e.g., active, inactive).
- **Index**: The index value of the validator, which is determined by the order in which they joined the validator set. Validators with identical stakes are typically ordered deterministically, with those who joined earlier having a lower index.

## High-Level Diagram

Below is a high-level diagram of the TinyChain architecture:

```
+-------------------+
|      Wallet       |
+-------------------+
         |
         v
+-------------------+
|        API        |
+-------------------+
         |
         v
+-------------------+
|      Node         |
| +---------------+ |
| | Transaction   | |
| |     Pool      | |
| +---------------+ |
| +---------------+ |
| |     Forger    | |
| +---------------+ |
| +---------------+ |
| | Storage Engine| |
| +---------------+ |
| +---------------+ |
| | Validation    | |
| |    Engine     | |
| +---------------+ |
| +---------------+ |
| | TinyVM Engine | |
| +---------------+ |
+-------------------+
```

The diagram illustrates the main components of TinyChain and their interactions. The wallet interacts with the API to send transactions and query the blockchain state. The API communicates with the node, which consists of several sub-components responsible for maintaining the blockchain, validating transactions, and executing smart contracts.
