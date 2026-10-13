# Step 1 & Step 2: Solana Market Research & Selection

**Project:** SVM-accurate simulation tool for exploring arbitrage loops and oracle vulnerabilities using AI agents  
**Intern:** [@Rizz-1024](https://github.com/Rizz-1024)  
**Supervisor / Reviewer:** [@andrew-octopus](https://github.com/andrew-octopus)  

---

## Step 1: Researching Solana Markets

To model arbitrage loops and oracle interactions in an SVM simulation environment (LiteSVM), we examined major Solana decentralized trading venues:

### 1. JTX (Jito Tip Exchange / MEV & Swap Markets)
* **Overview:** JTX / Jito MEV infrastructure focuses on transaction bundling, atomic execution, and tip-based arbitrage mechanics on Solana.
* **Mechanism:** Relies on searcher bundles and MEV block-engine ordering to execute risk-free backruns and arbitrage loops.
* **Relevance for Project:** Critical for modeling MEV-aware arbitrage loops, priority fees, and bundle atomicity.
* **LiteSVM Suitability:** Requires bundling simulation or mock tip payment accounts; highly complementary when paired with AMM pools.

### 2. Orca Whirlpools (Concentrated Liquidity AMM - CLMM)
* **Program ID:** whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc
* **Mechanism:** Concentrated liquidity market maker using discrete tick arrays (similar to Uniswap v3). Traders swap tokens through pools with defined fee tiers (e.g., 1 bps, 5 bps, 30 bps, 100 bps).
* **Open Source:** Program binary and IDL are fully open source on GitHub (orca-so/whirlpools).
* **LiteSVM Suitability:** **Excellent.** The compiled SBF program (whirlpool.so) can be directly loaded into LiteSVM memory without needing live validator RPCs. Swap instructions (swap, swap_v2) are completely deterministic.

### 3. Phoenix (Central Limit Order Book - CLOB)
* **Program ID:** PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY
* **Mechanism:** Fully on-chain central limit order book built by Ellipsis Labs. Eliminates asynchronous cranking by settling trades atomically within a single transaction.
* **LiteSVM Suitability:** **Very High.** Provides zero-crank atomic matching, perfect for evaluating latency-sensitive arbitrage agents.

### 4. Raydium (CPMM / Concentrated Liquidity)
* **Program ID:** 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 (AMM v4) / CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK (CLMM)
* **Mechanism:** High-volume automated market maker integrated with OpenBook/Serum order routing and standalone liquidity pools.
* **LiteSVM Suitability:** Moderate. Program state dependencies are slightly more complex to mock offline in minimal SVM fixtures.

---

## Step 2: Market Selection for LiteSVM Simulation

### Chosen Market: **Orca Whirlpools (CLMM)**

### Justification:
1. **Accurate Arbitrage Modeling:** Concentrated liquidity allows AI agents to explore price slippage, tick crossing, and pool rebalancing—ideal for discovering non-trivial arbitrage loops.
2. **Deterministic SVM Execution:** Whirlpool swap instructions execute synchronously and deterministically in a single instruction, which matches the execution model of **LiteSVM**.
3. **Reproducible Test Fixtures:** The Whirlpool bytecode (whirlpool.so) and account layouts can be extracted or built and loaded directly into LiteSVM via Python bindings (litesvm).
4. **Clean Interface for Step 4:** Allows a straightforward setup for:
   - Creating mints (e.g. Token A and Token B)
   - Initializing a Whirlpool market with fixed initial liquidity
   - Airdropping tokens to **Alice** and **Bob**
   - Executing trades and inspecting before/after token balances

---

## Next Step (Step 4 Preview)
With **Step 3 (Tooling)** already verified (Solana CLI, Anchor, and Rust installed in WSL), we will proceed to write the **LiteSVM simulation script** in early-code/ where Alice and Bob execute trades against this market structure.
