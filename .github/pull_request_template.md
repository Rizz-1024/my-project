## 1. High-Level Summary
<!-- Concise summary of what this PR does and why it is needed. -->

### Architecture Overview
```mermaid
flowchart TD
    subgraph Host["Host Environment (Python)"]
        Client["Execution Client (early-code/raydium.py)"]
        Signer["Developer Wallet (~/.config/solana/id.json)"]
    end

    subgraph LiteSVM["LiteSVM In-Process Solana VM"]
        subgraph Programs["Loaded Bytecode (.so)"]
            AMM["raydium_amm.so (Raydium AMM V4)"]
            SPL["spl_token.so (SPL Token Program)"]
            SRM["serum_dex.so (Serum DEX)"]
        end

        subgraph Accounts["Mainnet State Snapshots (.json)"]
            Pool["raydium_pool.json"]
            CVault["coin_vault.json (SOL Reserve)"]
            PVault["pc_vault.json (USDC Reserve)"]
            Orders["open_orders.json / market.json"]
        end
    end

    Client -->|Dispatches Swap Instruction| AMM
    AMM -->|Transfers Tokens| SPL
    AMM -->|Reads/Updates Reserves| CVault
    AMM -->|Reads/Updates Reserves| PVault
