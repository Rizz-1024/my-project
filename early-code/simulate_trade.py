"""
simulate_trade.py - LiteSVM Trade Simulation

Simulates Alice and Bob trading on a constant-product SOL/USDC market
"""

from typing import Dict
from solders.litesvm import LiteSVM
from solders.keypair import Keypair
from solders.pubkey import Pubkey


LAMPORTS_PER_SOL = 1_000_000_000       # 1 SOL = 10^9 lamports
USDC_UNITS_PER_TOKEN = 1_000_000      # 1 USDC = 10^6 micro-units (6 decimals)
BPS_DENOMINATOR = 10_000              # 10,000 basis points = 100%
DEFAULT_FEE_BPS = 30                  # 30 bps = 0.3% fee


class MarketPool:
    def __init__(self, address: Pubkey, vaults: Dict[str, int], fee_bps: int = DEFAULT_FEE_BPS):
        self.address = address
        self.vaults = vaults
        self.fee_bps = fee_bps

    def quote_swap(self, from_token: str, to_token: str, amount_in: int) -> int:
        """Constant product AMM formula: dy = (y * dx * (1 - fee)) / (x + dx * (1 - fee))"""
        reserve_in = self.vaults[from_token]
        reserve_out = self.vaults[to_token]
        amount_in_with_fee = amount_in * (BPS_DENOMINATOR - self.fee_bps)
        numerator = amount_in_with_fee * reserve_out
        denominator = (reserve_in * BPS_DENOMINATOR) + amount_in_with_fee
        return numerator // denominator

    def swap(self, from_token: str, to_token: str, amount_in: int) -> int:
        amount_out = self.quote_swap(from_token, to_token, amount_in)
        self.vaults[from_token] += amount_in
        self.vaults[to_token] -= amount_out
        return amount_out


def format_balance(balances: Dict[str, int]) -> str:
    sol = balances["SOL"] / LAMPORTS_PER_SOL
    usdc = balances["USDC"] / USDC_UNITS_PER_TOKEN
    return f"{sol:.4f} SOL, {usdc:.2f} USDC"


def main():
    # Initialize LiteSVM in-process VM
    svm = LiteSVM()

    #  Create keypairs for Alice and Bob
    alice = Keypair()
    bob = Keypair()

    print("--- Wallets Created ---")
    print(f"Alice: {alice.pubkey()}")
    print(f"Bob:   {bob.pubkey()}\n")

    #  Initialize market pool with 100 SOL and 15,000 USDC reserves
    market_address = Keypair().pubkey()
    market = MarketPool(
        address=market_address,
        vaults={
            "SOL": 100 * LAMPORTS_PER_SOL,
            "USDC": 15_000 * USDC_UNITS_PER_TOKEN,
        },
        fee_bps=DEFAULT_FEE_BPS,
    )

    print("--- Market Initialized ---")
    print(f"Pool Address: {market.address}")
    print(f"Initial Reserves: {format_balance(market.vaults)}\n")

    # Airdrop native SOL on LiteSVM
    svm.airdrop(alice.pubkey(), 10 * LAMPORTS_PER_SOL)
    svm.airdrop(bob.pubkey(), 2 * LAMPORTS_PER_SOL)

    # Track user balances in integer base units
    alice_balances = {
        "SOL": svm.get_balance(alice.pubkey()),
        "USDC": 100 * USDC_UNITS_PER_TOKEN,
    }
    bob_balances = {
        "SOL": svm.get_balance(bob.pubkey()),
        "USDC": 1_500 * USDC_UNITS_PER_TOKEN,
    }

    # Print initial token balances
    print("--- Initial Balances ---")
    print(f"Alice: {format_balance(alice_balances)}")
    print(f"Bob:   {format_balance(bob_balances)}\n")

    #  Execute trades
    print("--- Executing Trades ---")

    # Alice swaps 2 SOL for USDC
    alice_sol_in = 2 * LAMPORTS_PER_SOL
    alice_usdc_out = market.swap("SOL", "USDC", alice_sol_in)
    alice_balances["SOL"] -= alice_sol_in
    alice_balances["USDC"] += alice_usdc_out
    print(f"Alice swapped {alice_sol_in / LAMPORTS_PER_SOL:.2f} SOL -> {alice_usdc_out / USDC_UNITS_PER_TOKEN:.2f} USDC")

    # Bob swaps 500 USDC for SOL
    bob_usdc_in = 500 * USDC_UNITS_PER_TOKEN
    bob_sol_out = market.swap("USDC", "SOL", bob_usdc_in)
    bob_balances["USDC"] -= bob_usdc_in
    bob_balances["SOL"] += bob_sol_out
    print(f"Bob swapped {bob_usdc_in / USDC_UNITS_PER_TOKEN:.2f} USDC -> {bob_sol_out / LAMPORTS_PER_SOL:.4f} SOL\n")

    # Print new balances after trades
    print("--- Final Balances ---")
    print(f"Alice: {format_balance(alice_balances)}")
    print(f"Bob:   {format_balance(bob_balances)}")
    print(f"Market Pool Reserves: {format_balance(market.vaults)}")


if __name__ == "__main__":
    main()
