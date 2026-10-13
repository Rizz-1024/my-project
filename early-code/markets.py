"""
markets.py - Market configurations and simulation definitions
for Solana SVM-accurate simulation project (Step 1 & 2).

Internship Project - Sep 2026
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketConfig:
    name: str
    program_id: str
    market_type: str
    description: str
    selected: bool = False


# Step 1: Researched Solana Markets
SOLANA_MARKETS = {
    "JTX": MarketConfig(
        name="JTX / Jito MEV",
        program_id="T1pyyaTNZsKv2WcRAB8oVnk93mLJw2XzjtVYqCsaHqt",
        market_type="MEV / Bundle Tip & Order Execution",
        description="Jito transaction bundle and tip exchange mechanism for atomic arbitrage execution.",
        selected=False,
    ),
    "ORCA_WHIRLPOOLS": MarketConfig(
        name="Orca Whirlpools",
        program_id="whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
        market_type="Concentrated Liquidity AMM (CLMM)",
        description="Tick-based concentrated liquidity pool with deterministic single-instruction swaps.",
        selected=True,  # Step 2: Chosen market
    ),
    "PHOENIX": MarketConfig(
        name="Phoenix (Ellipsis Labs)",
        program_id="PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY",
        market_type="Central Limit Order Book (CLOB)",
        description="Instant settlement, non-cranked on-chain orderbook.",
        selected=False,
    ),
    "RAYDIUM": MarketConfig(
        name="Raydium AMM",
        program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
        market_type="Constant Product / Hybrid AMM",
        description="High-volume automated market maker on Solana.",
        selected=False,
    ),
}


def get_chosen_market() -> MarketConfig:
    """Return the selected market for Step 2."""
    for market in SOLANA_MARKETS.values():
        if market.selected:
            return market
    raise ValueError("No market selected.")


if __name__ == "__main__":
    chosen = get_chosen_market()
    print("==================================================")
    print(" Solana Market Selection (Step 1 & Step 2)")
    print("==================================================")
    print(f"Selected Market : {chosen.name}")
    print(f"Program ID      : {chosen.program_id}")
    print(f"Market Type     : {chosen.market_type}")
    print(f"Description     : {chosen.description}")
    print("==================================================")
    print("Ready for Step 4 (LiteSVM Alice & Bob trading script).")
