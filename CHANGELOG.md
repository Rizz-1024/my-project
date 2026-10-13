# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Jito ShredStream and Geyser gRPC direct pipe integration for sub-slot memory ingestion.
- Cross-program invocation (CPI) atomic bundling program written in Rust for single-transaction circular execution on Mainnet.

---

## [0.5.0] - 2026-10-11 — Multi-Market Circular Arbitrage & Optimal Trade Sizing Engine

### Added
- **`early-code/multi_market_arbitrage.py`**:
  - **Multi-Protocol Venue Registry:** Comprehensive liquidity graph integrating Raydium AMM V4 ($x \cdot y = k$ + Serum Hybrid CLOB), Orca Whirlpools (Concentrated Liquidity CLMM $\sqrt{P}$ Q64.64), Raydium CLMM/CP-Swap, and Meteora DLMM dynamic liquidity bin corridors.
  - **Multi-Token Basket Coverage:** Support for high-volume SPL assets: Wrapped SOL (`So11111111111111111111111111111111111111112`), USDC (`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`), BONK (`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`), and JitoSOL (`J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn`).
  - **Closed-Loop Circular Invariant:** Zero-inventory delta neutral architecture evaluating closed cyclic routing graphs:
    - 2-hop spatial cycles: `SOL -> Venue A -> USDC -> Venue B -> SOL` and `USDC -> Venue A -> SOL -> Venue B -> USDC`.
    - 3-hop triangular cycles: `SOL -> BONK -> USDC -> SOL`.
  - **Calculus-Based Optimal Trade Sizing Engine:** Exact analytical derivation computing the point of zero marginal profit ($\frac{d\Pi}{dx} = 0$) balancing pool quadratic slippage against transaction fees:
    $$\Delta x^* = \frac{\sqrt{R_{A,1} \cdot R_{A,2} \cdot R_{B,1} \cdot R_{B,2} \cdot \gamma_A \cdot \gamma_B} - R_{A,1} \cdot R_{B,2}}{\gamma_B \cdot R_{A,2} + R_{B,2}}$$
    where $\gamma_k = 1 - \frac{\text{fee\_bps}_k}{10000}$ accounts for pool-level fee retention.
  - **Zero-Profit Ceiling Enforcement ($2x^*$):** Mathematical calculation of the exact point where price impact exhausts initial arbitrage spread ($\Delta x_{\text{zero\_profit}} \approx 2 \Delta x^*$). Execution automatically bounds trade sizing to $\min(x^*, \text{Available Wallet Stock})$, incorporating on-chain base gas deductions (5,000 lamports).
  - **Parallel Multithreaded Concurrency:** Candidate route evaluation executed across `concurrent.futures.ThreadPoolExecutor(max_workers=6)` for sub-millisecond memory computation.
  - **Local LiteSVM Validation Harness:** In-memory validation testing trades against compiled smart contract binaries in `fixtures/contracts/`.
  - **Out-of-the-Box Zero-Argument Execution:** Default execution runs 10 clean verification iterations and exits with status code 0.

---

## [0.4.0] - 2026-10-08 — Two-Way Circular Arbitrage & Real-Time Latency Simulation Harness

### Added
- **`early-code/circular_arbitrage.py`**:
  - **Two-Way Closed-Loop Engine:** Spatial loop engine eliminating directional holding risk by evaluating 4 simultaneous cycles (`SOL -> SOL` and `USDC -> USDC`) between Raydium AMM V4 and Orca Whirlpools.
  - **Parallel Worker Concurrency:** High-frequency 100 ms polling loop distributing candidate cycle scoring across `concurrent.futures.ThreadPoolExecutor(max_workers=4)`.
  - **Fee & Liquidity Friction Math:** Integrates Raydium 25 bps fees and Orca Whirlpool 4 bps concentrated liquidity tick friction (~29 bps combined spread threshold).
  - **Anchor IDL Instruction Dispatch:** Low-level instruction packing utilizing Anchor method selector `0xf8c69e91e17587c8` and exact 12-account vector resolution into LiteSVM.

- **`early-code/live_arbitrage_monitor.py`**:
  - **Live Mainnet JSON-RPC Sampler:** Live state polling extracting 64-bit raw reserve bytes from Raydium vault accounts (offsets `64..72`) alongside Q64.64 sqrt-price curves from Orca Whirlpools (offsets `65..81`).
  - **Divergence Detection Engine:** Automatic trigger flagging dual-market price spreads exceeding 0.03% divergence.
  - **Network Propagation Latency Simulation:** Enforces a 400 ms propagation delay modeling validator mempool queuing and block leadership transit.
  - **On-Chain Slippage Reversion:** Re-queries live pool states at slot $T_1$ and executes the trade inside LiteSVM. Demonstrates smart contract protection through programmatic revert (`Custom(30): Exceeded desired slippage limit`) when pool reserves shift during latency windows.

---

## [0.3.0] - 2026-09-28 — Structured On-Chain Fixtures & Raydium AMM V4 Parser Suite

### Added
- **`fixtures/contracts/` (Compiled Berkeley Packet Filter Binaries):**
  - `raydium_amm.so`: Compiled BPF bytecode for Raydium AMM V4 smart contract enforcing constant-product curves, open orders math, and 25 bps fee calculations.
  - `whirlpool.so`: Compiled BPF bytecode for Orca Whirlpool concentrated liquidity engine dumped from Mainnet ProgramData account `CtXfPzz36dH5Ws4UYKZvrQ1Xqzn42ecDW6y8NKuiN8nD`.
  - `spl_token.so`: Canonical Solana Program Library (SPL) Token program managing token mints, vault debits, and balance transfers.
  - `serum_dex.so`: Serum / OpenBook orderbook engine required by Raydium AMM V4 for hybrid liquidity verification.
  - `raydium_cp_swap.so`: Reference BPF bytecode for Raydium Constant-Product swap execution.
- **`fixtures/accounts/` (Mainnet Ledger State Snapshots):**
  - Account state dumps: `raydium_pool.json`, `coin_vault.json`, `pc_vault.json`, `open_orders.json`, `target_orders.json`, `market.json`, `bids.json`, `asks.json`, `event_q.json`, `market_coin_vault.json`, `market_pc_vault.json`.
  - `manifest.json`: Structured JSON catalog detailing public keys, byte lengths, owners, and descriptions for all serialized accounts.
- **`early-code/parse_pool.py` & `early-code/parse_market.py`**:
  - Binary unpackers extracting Raydium AMM state layouts and Serum orderbook memory slabs.
- **`early-code/simulate_raydium_trade.py`**:
  - Low-level trade simulation script validating raw instruction layout across Raydium AMM V4 vaults inside LiteSVM.

---

## [0.2.0] - 2026-09-14 — Market Research & Baseline LiteSVM Swap Simulation

### Added
- **`early-code/MARKET_SELECTION.md`**:
  - Detailed comparative research on Solana trading venues: JTX (Jito MEV/bundle), Phoenix (central limit order book), Raydium V4, and Orca Whirlpools (CLMM).
  - Defined protocol trade-offs regarding fee tiers, liquidity fragmentation, and tick math complexity.
- **`early-code/markets.py`**:
  - Market data structures and venue parameters for Solana DEX protocols.
- **`early-code/simulate_trade.py`**:
  - Baseline LiteSVM transaction simulation demonstrating wallet initialization, SPL token minting, simulated native airdrops, and constant-product AMM swap execution between Alice and Bob.
- **PR CI/CD Quality Controls**:
  - GitHub PR title linting workflow (`.github/workflows/pr-title-check.yml`) enforcing semantic commit standards.
  - Standardized pull request templates for features, bugfixes, and hotfixes.

---

## [0.1.0] - 2026-08-30 — Initial Repository Setup & Foundation

### Added
- Initialized repository for Solana SVM simulation and trading research.
- Configured Python virtual environment tooling and `.gitignore`.
- Established initial `CHANGELOG.md` tracking Keep a Changelog conventions.
- Created preliminary `README.md` introducing project scope and simulation objectives.
