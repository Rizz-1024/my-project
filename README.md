# Name

**Internship Project for Solana Development**

---

## Description

This project provides an SVM-accurate, local on-chain simulation and execution testing framework for decentralized finance (DeFi) trading protocols on the Solana blockchain.

### Background & Context
Testing decentralized trading algorithms and market makers on Solana typically introduces significant engineering friction:
- **Mainnet Deployments:** Incur real capital risk, network transaction fees, and adverse price slippage.
- **Devnet Environments:** Feature stale, abandoned liquidity pools, missing peripheral protocol accounts, and intermittent RPC node unreliability.
- **Off-Chain Mocking (Python / TypeScript):** Relies on mathematical approximations that bypass low-level Berkeley Packet Filter (BPF) runtime panics, account serialization quirks, compute unit limits, and Cross-Program Invocation (CPI) constraints.

This project solves these limitations by implementing a **local, deterministic execution harness powered by LiteSVM** (an in-process Solana Virtual Machine runtime). Instead of simulating trades through Python math or mock vaults, this suite loads real compiled Solana program bytecode (`.so`) and hydrates the VM ledger with serialized account state snapshots (`.json`) dumped directly from Solana Mainnet-Beta. This delivers microsecond-level execution benchmarks with zero network latency, zero transaction fees, and 100% cryptographic and state fidelity to Mainnet.

### Features & Differentiating Capabilities
- **Multi-Venue Market Research (`feat/market-selection`):** In-depth technical taxonomy comparing Solana's primary trading architectures:
  - **Orca Whirlpools:** Concentrated Liquidity AMM (CLMM) utilizing localized tick arrays for capital efficiency.
  - **Phoenix (Ellipsis Labs):** Instant settlement, non-cranked Central Limit Orderbook (CLOB).
  - **Raydium AMM V4:** Deep-liquidity hybrid AMM combining constant-product pools with Serum/OpenBook order routing.
  - **Jito MEV / JTX:** Atomic transaction bundles and tip mechanisms designed for sandwich-resistant execution.
- **Simulated Constant-Product Pool (`early-code/simulate_trade.py`):** Models multi-party trading (Alice & Bob) with integer-scaled token precision ($10^9$ lamports for SOL, $10^6$ units for USDC) and 30 bps fee accounting.
- **Direct On-Chain Raydium V4 Execution Client (`early-code/raydium.py`):**
  - Executes directly against official compiled smart contracts: `raydium_amm.so`, `spl_token.so`, and `serum_dex.so`.
  - Hydrates real Mainnet liquidity from 11 account state fixtures holding **157,470.6015 SOL** and **19,158,073.74 USDC**.
  - Derives deterministic SPL Associated Token Accounts (ATAs) and provisions rent-exempt balances (`2,039,280` lamports for 165 bytes).
  - Assembles raw binary instruction payloads for Raydium Swap (Instruction Index 9) with exact 18-account metadata configurations (`is_signer`, `is_writable`).
  - Reads post-trade token balances directly from SPL Token byte layouts (offsets 64..72) and monitors compute units (~18,552 CUs).
- **Mathematical Invariant Verification:** Verifies continuous constant-product preservation ($x \cdot y = k$) with 25 bps pool fee deductions and dynamic slippage tolerance bounds (`min_amount_out`).

### Program Binaries (`.so`) & Mainnet Account Fixtures (`.json`)
To eliminate mocked balances and fake Python math, LiteSVM directly executes official BPF shared object binaries against frozen Mainnet account snapshots:

| File Location | Type | Address / Program ID | Functional Role in LiteSVM |
| :--- | :--- | :--- | :--- |
| `fixtures/raydium_amm.so` | Program Binary | `675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8` | Core Raydium AMM V4 contract; executes swap math, fee deduction (25 bps), and slippage checks. |
| `fixtures/spl_token.so` | Program Binary | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | Official SPL Token program; executes balance debits, credits, and ATA initialization. |
| `fixtures/serum_dex.so` | Program Binary | `srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX` | Serum DEX / OpenBook program; required by Raydium for hybrid orderbook state validation. |
| `fixtures/raydium_pool.json` | Account Snapshot | `58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2` | SOL/USDC pool state with status flags, fee rates, and vault pointers. |
| `fixtures/coin_vault.json` | Account Snapshot | `DQyrAcCrDXQ7NeoqGgDCZwBvWDcYmFCjSb9JtteuvPpz` | Live WSOL token vault holding **157,470.6015 SOL** real reserves. |
| `fixtures/pc_vault.json` | Account Snapshot | `HLmqeL62xR1QoZ1HKKbXRrdN1p3phKpxRMb2VVopvBBz` | Live USDC token vault holding **19,158,073.74 USDC** real reserves. |
| `fixtures/open_orders.json` | Account Snapshot | `HRk9CMrpq7Jn9sh7mzxE8CChHG8dneX9TXE7j13bPR72` | Raydium tracking account for orders placed on the Serum orderbook. |
| `fixtures/target_orders.json` | Account Snapshot | `CZza3Ej4Mc58MnxWA385itKujMYYiRwBfZLq7wn99u9g` | Target rebalancing account used by Raydium to manage Serum order depths. |
| `fixtures/market.json` | Account Snapshot | `9wFFyRfZBsuAha4YcuxcXLKwMxJR43S7fPfQLusDBzvT` | Serum SOL/USDC market configuration account. |
| `fixtures/bids.json` / `asks.json` | Account Snapshots | Orderbook Slabs | Serum buy/sell orderbook slab trees required for market state verification. |
| `fixtures/event_q.json` | Account Snapshot | Event Queue | Serum trade execution and settlement queue account. |
| `fixtures/market_coin_vault.json` | Account Snapshot | Serum WSOL Vault | Serum internal token vault referenced in swap account inputs. |
| `fixtures/market_pc_vault.json` | Account Snapshot | Serum USDC Vault | Serum internal quote vault referenced in swap account inputs. |

---

## Badges

[![Solana](https://img.shields.io/badge/Solana-Mainnet--Beta-black?logo=solana)](https://solana.com)
[![Engine](https://img.shields.io/badge/Engine-LiteSVM-blueviolet)](https://github.com/jito-foundation/litesvm)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![GitLab](https://img.shields.io/badge/GitLab-Multi--Branch%20Sprint-orange?logo=gitlab)](https://gitlab.com/mister_octopus/scorpion_iinternship_project/-/branches)

---

## Visuals

### System Architecture & Cross-Program Invocation Flow

```mermaid
graph TD
    User[Trader Signer Keypair] -->|Signs Transaction| Client[Execution Client: raydium.py]
    Client -->|Instruction Index 9| AMM[Raydium AMM V4 Program]
    AMM -->|Validates Liquidity Depth| Orderbook[Serum DEX Orderbook]
    AMM -->|Constant Product Invariant| PoolState[Raydium Pool State]
    AMM -->|Cross Program Invocation| SPL[SPL Token Program]
    SPL -->|Debits 2.0 SOL| UserWSOL[Trader WSOL Account]
    SPL -->|Credits 2.0 SOL| CoinVault[SOL Vault: 157470 SOL]
    SPL -->|Debits 242.71 USDC| PCVault[USDC Vault: 19158073 USDC]
    SPL -->|Credits 242.71 USDC| UserUSDC[Trader USDC Account]
```

---

## Installation

### Prerequisites & System Packages
Updates package repositories and installs fundamental Linux build utilities, C/C++ compilers, linkers, LLVM toolchains, and SSL cryptographic headers required to compile Rust crates and Solana binaries:

```bash
sudo apt update && sudo apt install -y \
    build-essential \
    pkg-config \
    libudev-dev \
    llvm \
    clang \
    cmake \
    libssl-dev \
    curl \
    git
```

### 1. Install Rust Toolchain
Downloads and runs the official Rustup installer, configuring the `rustc` compiler and `cargo` package manager in non-interactive mode:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
```

Loads Cargo environment variables into the current terminal session so that `rustc` and `cargo` commands become immediately accessible without needing a terminal restart:
```bash
source $HOME/.cargo/env
```

Queries the active Rust toolchain to verify that both the compiler and package manager are installed correctly and ready for use:
```bash
rustc --version
cargo --version
```

### 2. Install Solana CLI Toolsuite
Downloads and executes the official Anza/Agave installer script to install the Solana CLI tools and BPF compilation engine:
```bash
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
```

Temporarily appends the Solana active release binary folder to your current session's `PATH` variable for immediate terminal access:
```bash
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
```

Permanently writes the Solana binary path into your user's `~/.bashrc` configuration file so that the `solana` command is automatically available in every future terminal window:
```bash
echo 'export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"' >> ~/.bashrc
```

Queries the Solana executable to verify that the CLI binary is properly linked and displays the installed version:
```bash
solana --version
```

### 3. Install Anchor CLI (via Anchor Version Manager - AVM)
Downloads and compiles the Anchor Version Manager (`avm`) from the official GitHub repository using Cargo, locking dependencies to prevent build breakage:
```bash
cargo install --git https://github.com/coral-xyz/anchor avm --locked --force
```

Uses the newly installed AVM tool to fetch and compile the latest stable release of the Anchor smart contract development framework:
```bash
avm install latest
```

Activates the compiled Anchor release as your global default development version:
```bash
avm use latest
```

Checks the active Anchor binary version to confirm successful compilation and system linkage:
```bash
anchor --version
```

### 4. Clone the Repository
Clones the complete project repository from GitLab onto your local disk, including all branches, code files, and Mainnet fixture snapshots:
```bash
git clone https://gitlab.com/mister_octopus/scorpion_iinternship_project.git
```

Changes your current working directory to navigate inside the cloned project root folder:
```bash
cd scorpion_iinternship_project
```

### 5. Setup Python Environment & LiteSVM
Creates an isolated Python virtual environment named `solana_env` in your user home directory to avoid package version collisions with system Python:
```bash
python3 -m venv ~/solana_env
```

Activates the virtual environment so that subsequent Python packages are installed strictly inside this sandbox:
```bash
source ~/solana_env/bin/activate
```

Upgrades Python's package management tool (`pip`) to the newest release to support modern pre-compiled wheel distributions:
```bash
pip install --upgrade pip
```

Installs `solders` (v0.21.0), the Solana Python SDK providing C-bindings for Solana primitives and the in-process LiteSVM runtime engine:
```bash
pip install solders==0.21.0
```

### 6. Generate Developer Keypair
Generates a new ed25519 Solana cryptographic keypair without a BIP39 passphrase prompt and writes it to Solana's default config path:
```bash
solana-keygen new --no-bip39-passphrase -o ~/.config/solana/id.json
```

Reads the keypair file and outputs its corresponding base58-encoded public key (wallet address) to the terminal:
```bash
solana address
```

---

## Usage

### 1. Direct Raydium AMM V4 On-Chain Swap (LiteSVM)

Execute a direct on-chain swap from **SOL to USDC**:
```bash
python early-code/raydium.py --direction sol-to-usdc --amount 2.0
```

**Expected Terminal Output:**
```text
--- Raydium AMM V4 Direct On-Chain Execution ---
Signer Wallet:      GzdXR3tkDMgjVvzVCXj1YvCqW6VnSGSrk4wJ3Sn6LqNt
Raydium Pool:       58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2
SOL Vault Reserve:  157,470.6015 SOL
USDC Vault Reserve: 19,158,073.74 USDC

Executing Swap:     2.0000 SOL -> USDC
Expected Output:    242.7112 USDC
Slippage Limit:     241.4976 USDC (50 bps)
Status:             Confirmed by Raydium smart contract
Compute Units:      18,552

Output Received:    +242.7112 USDC
Updated SOL Vault:  157,472.6015 SOL
Updated USDC Vault: 19,157,831.03 USDC
```

Execute a reverse swap from **USDC to SOL**:
```bash
python early-code/raydium.py --direction usdc-to-sol --amount 200.0
```

### 2. Standalone Constant-Product Pool Simulation
Simulate multi-party token swaps between Alice and Bob:
```bash
python early-code/simulate_trade.py
```

### 3. Market Research & Venue Configurations
Inspect researched market configurations and selection parameters:
```bash
python early-code/markets.py
```

### 4. Diagnostic & Account Loading Verification
Run tests verifying LiteSVM account hydration and keypair loading:
```bash
python early-code/test_litesvm_load.py
python early-code/test_account_load.py
python early-code/test_load_keypair.py
```

---

## Support



---

## Roadmap

- [x] **Step 1: Solana Market Research (`feat/market-selection`)** — In-depth architectural analysis of JTX, Orca Whirlpools, Phoenix, and Raydium.
- [x] **Step 2: Market Selection (`feat/market-selection`)** — Documentation of selection rationale in `early-code/MARKET_SELECTION.md` and definitions in `markets.py`.
- [x] **Step 3: Tooling & Environment Setup** — Local WSL2, Solana CLI, Anchor, and Python Solders environment configuration.
- [x] **Step 4: LiteSVM Trading & AMM Simulation (`feat/litesvm-simulation`)**
  - [x] **Part A:** In-process constant-product pool simulation modeling Alice & Bob trades (`simulate_trade.py`).
  - [x] **Part B:** Direct Raydium AMM V4 on-chain client (`raydium.py`) using Mainnet bytecode binaries and account snapshots.
- [ ] **Step 5: Multi-Market Arbitrage Simulation** — Real-time price disparity detection and single-transaction atomic arbitrage execution between Raydium and secondary DEXs (Orca Whirlpools / Phoenix).

---

## Contributing

This repository follows a structured sprint workflow:

### Branch Structure
- `main` — Production baseline and stable releases.
- `feat/<feature-name>` — Feature development branches (e.g. `feat/market-selection`, `feat/litesvm-simulation`).
- `docs/<doc-name>` — Documentation and changelog tracking.
- `fix/<fix-name>` — Bug fixes and patches.

### Development Guidelines
1. Merge request (MR) titles and commit messages must strictly adhere to the [Conventional Commits](https://www.conventionalcommits.org/) specification (e.g. `feat: ...`, `fix: ...`, `docs: ...`).
2. All simulations and tests must execute cleanly with exit code 0 before MR submission.
3. `CHANGELOG.md` must be updated under `[Unreleased]` for any user-facing functional changes.

---

## Authors and acknowledgment

- **Developer:** Scorpion_Sign
- **Project Tutor / Reviewer:** Andrew-Octopus

---

## License



---

## Project status

Active development across sprint branches — Step 4 (Direct On-Chain Raydium Simulation) complete; Step 5 (Multi-Market Arbitrage) in preparation.