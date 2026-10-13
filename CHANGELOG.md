# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- **Step 1:** Completed market research on Solana trading venues: JTX (Jito MEV/bundle), Orca Whirlpools (CLMM), Phoenix (CLOB), and Raydium.
- **Step 2:** Documented market selection rationale in `early-code/MARKET_SELECTION.md` choosing **Orca Whirlpools** as the primary focus for LiteSVM simulation.
- Added Python market definition module in `early-code/markets.py`.
- **Step 4:** LiteSVM trade simulation script (`early-code/simulate_trade.py`) demonstrating wallet initialization, native airdrops, constant-product AMM swaps, and balance accounting for Alice and Bob.
- Added GitHub Actions workflow (`.github/workflows/pr-title-check.yml`) to enforce PR title naming conventions.

### Added
- Initialized repository for SVM simulation project
- Added `.gitignore` for Python project
- Created `CHANGELOG.md` to track project progress
- Created `README.md` with project description
