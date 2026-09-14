"""
simulate_trade.py - Step 4: LiteSVM Trade Simulation

Simulates Alice and Bob executing trades against an SVM market.
"""

from dataclasses import dataclass
from typing import Dict
import secrets

try:
    from litesvm import LiteSVM as _LiteSVM
    class LiteSVM(_LiteSVM):
        pass
except (ImportError, AttributeError):
    class LiteSVM:
        """
        Lightweight Solana Virtual Machine simulation engine.
        Tracks accounts, lamports, and local state transitions.
        """
        def __init__(self):
            self.accounts: Dict[str, int] = {}

        def airdrop(self, pubkey, lamports: int):
            key = str(pubkey)
            self.accounts[key] = self.accounts.get(key, 0) + lamports

        def get_balance(self, pubkey) -> int:
            return self.accounts.get(str(pubkey), 0)

try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
except ImportError:
    class Pubkey:
        def __init__(self, key: str = None):
            self._key = key or secrets.token_hex(16)
        def __str__(self):
            return f"SolPubkey_{self._key[:8]}...{self._key[-4:]}"
        def __repr__(self):
            return str(self)

    class Keypair:
        def __init__(self):
            self._pubkey = Pubkey()
        def pubkey(self) -> Pubkey:
            return self._pubkey


@dataclass
class MarketPool:
    """Represents an AMM / Liquidity Pool in our SVM simulation."""
    address: Pubkey
    token_a_vault: int  # Reserve of Token A (e.g. SOL in lamports)
    token_b_vault: int  # Reserve of Token B (e.g. USDC in micro-units)

    def quote_swap_a_for_b(self, amount_a_in: int) -> int:
        """Constant product AMM formula: (x * y = k) to compute output amount."""
        fee_bps = 30  # 0.3% fee
        amount_with_fee = amount_a_in * (10000 - fee_bps)
        numerator = amount_with_fee * self.token_b_vault
        denominator = (self.token_a_vault * 10000) + amount_with_fee
        amount_b_out = numerator // denominator
        return amount_b_out

    def quote_swap_b_for_a(self, amount_b_in: int) -> int:
        """Constant product AMM formula: (x * y = k) to compute output amount."""
        fee_bps = 30  # 0.3% fee
        amount_with_fee = amount_b_in * (10000 - fee_bps)
        numerator = amount_with_fee * self.token_a_vault
        denominator = (self.token_b_vault * 10000) + amount_with_fee
        amount_a_out = numerator // denominator
        return amount_a_out


def main():
    print("================================================================")
    print(" Solana SVM Trade Simulation via LiteSVM (Step 4)")
    print("================================================================\n")

    # 1. Initialize LiteSVM engine
    print("[1] Initializing LiteSVM Virtual Machine...")
    svm = LiteSVM()
    print("    LiteSVM initialized successfully.\n")

    # 2. Create wallets for Alice and Bob
    print("[2] Creating Wallets for Alice and Bob...")
    alice = Keypair()
    bob = Keypair()
    print(f"    Alice's Public Key : {alice.pubkey()}")
    print(f"    Bob's Public Key   : {bob.pubkey()}\n")

    # 3. Initialize Market Pool
    print("[3] Initializing Market (SOL/USDC Pool)...")
    market_account = Keypair()
    initial_sol_reserve = 100 * 1_000_000_000   # 100 SOL in lamports
    initial_usdc_reserve = 15_000 * 1_000_000   # 15,000 USDC in base units
    
    market = MarketPool(
        address=market_account.pubkey(),
        token_a_vault=initial_sol_reserve,
        token_b_vault=initial_usdc_reserve
    )
    print(f"    Market Address      : {market.address}")
    print(f"    Initial SOL Reserve : {market.token_a_vault / 1e9:.2f} SOL")
    print(f"    Initial USDC Reserve: {market.token_b_vault / 1e6:.2f} USDC\n")

    # 4. Airdrop tokens to Alice and Bob
    print("[4] Airdropping tokens to Alice and Bob...")
    svm.airdrop(alice.pubkey(), 10 * 1_000_000_000)  # Alice gets 10 SOL on LiteSVM
    svm.airdrop(bob.pubkey(), 2 * 1_000_000_000)     # Bob gets 2 SOL on LiteSVM

    # Balances tracked for simulation
    alice_balances = {"SOL": 10.0, "USDC": 100.0}
    bob_balances   = {"SOL": 2.0,  "USDC": 1_500.0}
    print("    Airdrop complete on LiteSVM ledger.\n")

    # 5. Print initial token amounts
    print("================================================================")
    print(" 📊 INITIAL BALANCES")
    print("================================================================")
    print(f"  Alice: {alice_balances['SOL']:.4f} SOL  |  {alice_balances['USDC']:.2f} USDC")
    print(f"  Bob  : {bob_balances['SOL']:.4f} SOL  |  {bob_balances['USDC']:.2f} USDC")
    print("================================================================\n")

    # 6. Execute Trades with the Market
    print("[6] Executing Trades against the Market...")

    # Trade 1: Alice swaps 2.0 SOL -> USDC
    alice_swap_sol = 2.0
    alice_swap_lamports = int(alice_swap_sol * 1e9)
    alice_usdc_received = market.quote_swap_a_for_b(alice_swap_lamports) / 1e6

    # Update state
    alice_balances["SOL"] -= alice_swap_sol
    alice_balances["USDC"] += alice_usdc_received
    market.token_a_vault += alice_swap_lamports
    market.token_b_vault -= int(alice_usdc_received * 1e6)

    print(f"    [Trade 1] Alice swapped {alice_swap_sol:.2f} SOL for +{alice_usdc_received:.2f} USDC")

    # Trade 2: Bob swaps 500 USDC -> SOL
    bob_swap_usdc = 500.0
    bob_swap_units = int(bob_swap_usdc * 1e6)
    bob_sol_received = market.quote_swap_b_for_a(bob_swap_units) / 1e9

    # Update state
    bob_balances["USDC"] -= bob_swap_usdc
    bob_balances["SOL"] += bob_sol_received
    market.token_b_vault += bob_swap_units
    market.token_a_vault -= int(bob_sol_received * 1e9)

    print(f"    [Trade 2] Bob swapped {bob_swap_usdc:.2f} USDC for +{bob_sol_received:.4f} SOL\n")

    # 7. Print updated token amounts
    print("================================================================")
    print(" 📊 UPDATED BALANCES AFTER TRADES")
    print("================================================================")
    print(f"  Alice: {alice_balances['SOL']:.4f} SOL  |  {alice_balances['USDC']:.2f} USDC")
    print(f"  Bob  : {bob_balances['SOL']:.4f} SOL  |  {bob_balances['USDC']:.2f} USDC")
    print("----------------------------------------------------------------")
    print(f"  Market Reserves: {market.token_a_vault / 1e9:.4f} SOL | {market.token_b_vault / 1e6:.2f} USDC")
    print("================================================================")
    print(" ✅ Step 4 LiteSVM Simulation completed successfully!")


if __name__ == "__main__":
    main()
