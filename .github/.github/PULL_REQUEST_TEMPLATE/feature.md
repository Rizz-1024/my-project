## Feature Description
<!-- What does this new capability or simulation step do? Why is it needed? -->

## Sprint Objective
<!-- Which roadmap step does this fulfill (e.g. Step 4: LiteSVM Direct Execution, Step 5: Multi-Market Arbitrage)? -->

## Technical Implementation
<!-- Explain the technical design, smart contracts interacted with, and accounts modified. -->

### Component & Data Flow
```mermaid
flowchart LR
    A["Client Input"] --> B["Instruction Construction"]
    B --> C["LiteSVM Execution Engine"]
    C --> D["On-Chain Program Bytecode (.so)"]
    D --> E["Updated Ledger State (.json)"]
