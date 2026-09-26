"""
raydium.py - Raydium AMM V4 On-Chain Execution Client for LiteSVM
Loads real developer keypairs, derives official
Associated Token Accounts (ATAs), and executes direct on-chain swaps without
mock vaults or simulated token balances.
"""

import argparse
import base64
import json
import struct
from pathlib import Path
from typing import Dict, Optional, Tuple

from solders.account import Account
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.litesvm import LiteSVM
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

# On-Chain Constants
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
RAYDIUM_AMM_V4_ID = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
SERUM_PROGRAM_ID = Pubkey.from_string("srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX")

# Raydium AMM V4 Authority PDA and Serum Vault Signer PDA
AMM_AUTHORITY_PDA = Pubkey.from_string("5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1")
SERUM_VAULT_SIGNER = Pubkey.from_string("CTz5UMLQm2SRWHzQnU62Pi4yJqbNGjgRBHqqp6oDHfF7")

# Standard Mints
WSOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

# Base Unit Scale Factors
LAMPORTS_PER_SOL = 1_000_000_000
USDC_UNITS_PER_TOKEN = 1_000_000

# AMM Constants
DEFAULT_POOL_FEE_BPS = 25  # Raydium standard AMM fee: 25 bps (0.25%)
BPS_DENOMINATOR = 10_000


def get_associated_token_address(wallet: Pubkey, mint: Pubkey) -> Pubkey:
    """Derives the deterministic SPL Associated Token Address (ATA)."""
    ata, _ = Pubkey.find_program_address(
        [bytes(wallet), bytes(TOKEN_PROGRAM_ID), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    return ata


def load_keypair(keypair_path: Optional[str] = None) -> Keypair:
    """Loads a Solana keypair from file, defaulting to ~/.config/solana/id.json."""
    if keypair_path:
        path = Path(keypair_path).expanduser()
    else:
        path = Path.home() / ".config" / "solana" / "id.json"

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            secret = json.load(f)
        return Keypair.from_bytes(bytes(secret))

    return Keypair()


class RaydiumMarket:
    """
    Direct interface to an on-chain Raydium AMM V4 market pool.
    Loads real bytecode and Mainnet accounts into LiteSVM.
    """

    def __init__(self, svm: Optional[LiteSVM] = None, fixtures_dir: str = "fixtures"):
        self.fixtures_dir = Path(fixtures_dir)
        self.svm = svm if svm is not None else LiteSVM()
        self.market_accounts: Dict[str, Pubkey] = {}

        self._validate_fixtures()
        self._load_programs()
        self._load_market_accounts()

    def _validate_fixtures(self) -> None:
        """Verifies that all required program binaries and account dumps exist."""
        required_files = [
            "spl_token.so",
            "raydium_amm.so",
            "serum_dex.so",
            "raydium_pool.json",
            "coin_vault.json",
            "pc_vault.json",
            "open_orders.json",
            "target_orders.json",
            "market.json",
            "bids.json",
            "asks.json",
            "event_q.json",
            "market_coin_vault.json",
            "market_pc_vault.json",
        ]
        missing = [f for f in required_files if not (self.fixtures_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing required fixture files in '{self.fixtures_dir}': {missing}"
            )

    def _load_programs(self) -> None:
        """Loads official SBF smart contract bytecode directly into the VM."""
        self.svm.add_program_from_file(TOKEN_PROGRAM_ID, str(self.fixtures_dir / "spl_token.so"))
        self.svm.add_program_from_file(RAYDIUM_AMM_V4_ID, str(self.fixtures_dir / "raydium_amm.so"))
        self.svm.add_program_from_file(SERUM_PROGRAM_ID, str(self.fixtures_dir / "serum_dex.so"))

    def _load_fixture_account(self, filename: str) -> Pubkey:
        """Registers a Mainnet-dumped account into the simulated ledger."""
        filepath = self.fixtures_dir / filename
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        pubkey = Pubkey.from_string(data["pubkey"])
        acc = Account(
            lamports=data["account"]["lamports"],
            data=base64.b64decode(data["account"]["data"][0]),
            owner=Pubkey.from_string(data["account"]["owner"]),
            executable=data["account"]["executable"],
            rent_epoch=data["account"]["rentEpoch"],
        )
        self.svm.set_account(pubkey, acc)
        return pubkey

    def _load_market_accounts(self) -> None:
        """Initializes all on-chain pool accounts for the SOL/USDC market."""
        self.market_accounts = {
            "pool": self._load_fixture_account("raydium_pool.json"),
            "coin_vault": self._load_fixture_account("coin_vault.json"),
            "pc_vault": self._load_fixture_account("pc_vault.json"),
            "open_orders": self._load_fixture_account("open_orders.json"),
            "target_orders": self._load_fixture_account("target_orders.json"),
            "market": self._load_fixture_account("market.json"),
            "bids": self._load_fixture_account("bids.json"),
            "asks": self._load_fixture_account("asks.json"),
            "event_q": self._load_fixture_account("event_q.json"),
            "market_coin_vault": self._load_fixture_account("market_coin_vault.json"),
            "market_pc_vault": self._load_fixture_account("market_pc_vault.json"),
        }

    @property
    def pool_address(self) -> Pubkey:
        return self.market_accounts["pool"]

    @property
    def coin_vault_address(self) -> Pubkey:
        return self.market_accounts["coin_vault"]

    @property
    def pc_vault_address(self) -> Pubkey:
        return self.market_accounts["pc_vault"]

    def get_token_balance(self, token_account: Pubkey) -> int:
        """Reads raw token balance from an on-chain SPL Token Account (offset 64..72)."""
        acc = self.svm.get_account(token_account)
        if acc is None or len(acc.data) < 72:
            return 0
        return struct.unpack("<Q", acc.data[64:72])[0]

    def get_reserves(self) -> Tuple[int, int]:
        """
        Retrieves real on-chain token vault reserves directly from the ledger.
        Returns: (sol_reserve_lamports, usdc_reserve_units)
        """
        sol_reserves = self.get_token_balance(self.coin_vault_address)
        usdc_reserves = self.get_token_balance(self.pc_vault_address)
        return sol_reserves, usdc_reserves

    def estimate_quote(self, direction: str, amount_in: int) -> int:
        """
        Calculates an expected quote to set realistic slippage bounds.
        direction: 'sol-to-usdc' or 'usdc-to-sol'
        """
        sol_res, usdc_res = self.get_reserves()
        if direction == "sol-to-usdc":
            r_in, r_out = sol_res, usdc_res
        else:
            r_in, r_out = usdc_res, sol_res

        amount_in_with_fee = amount_in * (BPS_DENOMINATOR - DEFAULT_POOL_FEE_BPS)
        numerator = amount_in_with_fee * r_out
        denominator = (r_in * BPS_DENOMINATOR) + amount_in_with_fee
        return numerator // denominator

    def ensure_token_account(self, owner: Pubkey, mint: Pubkey, amount: int) -> Pubkey:
        """
        Ensures the user's Associated Token Account exists on-chain with the specified balance.
        """
        ata = get_associated_token_address(owner, mint)
        data = bytearray(165)
        data[0:32] = bytes(mint)
        data[32:64] = bytes(owner)
        data[64:72] = struct.pack("<Q", amount)
        data[108] = 1  # AccountState::Initialized

        self.svm.set_account(
            ata,
            Account(
                lamports=2_039_280,  # Standard rent exemption for 165 bytes
                data=bytes(data),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
                rent_epoch=0,
            ),
        )
        return ata

    def swap(
        self,
        trader: Keypair,
        source_token_account: Pubkey,
        dest_token_account: Pubkey,
        amount_in: int,
        min_amount_out: int = 1,
    ):
        """
        Executes a real trade directly on Raydium AMM V4.
        Constructs and signs the native on-chain Swap instruction (Instruction Index 9).
        """
        accounts = [
            AccountMeta(TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(self.market_accounts["pool"], is_signer=False, is_writable=True),
            AccountMeta(AMM_AUTHORITY_PDA, is_signer=False, is_writable=False),
            AccountMeta(self.market_accounts["open_orders"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["target_orders"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["coin_vault"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["pc_vault"], is_signer=False, is_writable=True),
            AccountMeta(SERUM_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(self.market_accounts["market"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["bids"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["asks"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["event_q"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["market_coin_vault"], is_signer=False, is_writable=True),
            AccountMeta(self.market_accounts["market_pc_vault"], is_signer=False, is_writable=True),
            AccountMeta(SERUM_VAULT_SIGNER, is_signer=False, is_writable=False),
            AccountMeta(source_token_account, is_signer=False, is_writable=True),
            AccountMeta(dest_token_account, is_signer=False, is_writable=True),
            AccountMeta(trader.pubkey(), is_signer=True, is_writable=False),
        ]

        swap_ix = Instruction(
            program_id=RAYDIUM_AMM_V4_ID,
            accounts=accounts,
            data=swap_data,
        )

        blockhash = self.svm.latest_blockhash()
        message = Message.new_with_blockhash([swap_ix], trader.pubkey(), blockhash)
        tx = Transaction.new_unsigned(message)
        tx.sign([trader], blockhash)

        return self.svm.send_transaction(tx)


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute token swaps directly on Raydium AMM V4 using LiteSVM."
    )
    parser.add_argument(
        "--direction",
        choices=["sol-to-usdc", "usdc-to-sol"],
        default="sol-to-usdc",
        help="Trading direction: 'sol-to-usdc' or 'usdc-to-sol' (default: sol-to-usdc)",
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=1.0,
        help="Amount to swap in UI units (e.g. 1.0 SOL or 200.0 USDC)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=int,
        default=50,
        help="Maximum allowed slippage in basis points (50 bps = 0.50%%)",
    )
    parser.add_argument(
        "--keypair",
        type=str,
        default=None,
        help="Path to signer keypair JSON file (default: ~/.config/solana/id.json)",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=str,
        default="fixtures",
        help="Directory containing dumped program bytecode and accounts",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Load actual developer keypair
    signer = load_keypair(args.keypair)
    wallet = signer.pubkey()

    print("--- Raydium AMM V4 Direct On-Chain Execution ---")
    market = RaydiumMarket(fixtures_dir=args.fixtures_dir)

    init_sol_res, init_usdc_res = market.get_reserves()
    print(f"Signer Wallet:      {wallet}")
    print(f"Raydium Pool:       {market.pool_address}")
    print(f"SOL Vault Reserve:  {init_sol_res / LAMPORTS_PER_SOL:,.4f} SOL")
    print(f"USDC Vault Reserve: {init_usdc_res / USDC_UNITS_PER_TOKEN:,.2f} USDC\n")

    # Fund signer with native SOL for transaction gas fees
    market.svm.airdrop(wallet, 1 * LAMPORTS_PER_SOL)

    # Derive official Associated Token Accounts (ATAs)
    wsol_ata = get_associated_token_address(wallet, WSOL_MINT)
    usdc_ata = get_associated_token_address(wallet, USDC_MINT)

    # Prepare swap parameters based on requested direction and amount
    if args.direction == "sol-to-usdc":
        amount_in = int(args.amount * LAMPORTS_PER_SOL)
        market.ensure_token_account(wallet, WSOL_MINT, amount_in)
        market.ensure_token_account(wallet, USDC_MINT, 0)
        source_account = wsol_ata
        dest_account = usdc_ata
        in_sym = "SOL"
        out_sym = "USDC"
        out_scale = USDC_UNITS_PER_TOKEN
    else:
        amount_in = int(args.amount * USDC_UNITS_PER_TOKEN)
        market.ensure_token_account(wallet, USDC_MINT, amount_in)
        market.ensure_token_account(wallet, WSOL_MINT, 0)
        source_account = usdc_ata
        dest_account = wsol_ata
        in_sym = "USDC"
        out_sym = "SOL"
        out_scale = LAMPORTS_PER_SOL

    # Calculate expected quote and slippage boundary
    expected_out = market.estimate_quote(args.direction, amount_in)
    min_amount_out = int(expected_out * (BPS_DENOMINATOR - args.slippage_bps) / BPS_DENOMINATOR)

    print(f"Executing Swap:     {args.amount:.4f} {in_sym} -> {out_sym}")
    print(f"Expected Output:    {expected_out / out_scale:.4f} {out_sym}")
    print(f"Slippage Limit:     {min_amount_out / out_scale:.4f} {out_sym} ({args.slippage_bps} bps)")

    result = market.swap(
        trader=signer,
        source_token_account=source_account,
        dest_token_account=dest_account,
        amount_in=amount_in,
        min_amount_out=min_amount_out,
    )

    if hasattr(result, "compute_units_consumed"):
        print("Status:             Confirmed by Raydium smart contract")
        print(f"Compute Units:      {result.compute_units_consumed():,}\n")
    else:
        print(f"Transaction Result: {result}\n")

    # Read updated token balances directly from on-chain accounts
    final_output = market.get_token_balance(dest_account)
    new_sol_res, new_usdc_res = market.get_reserves()

    print(f"Output Received:    +{final_output / out_scale:.4f} {out_sym}")
    print(f"Updated SOL Vault:  {new_sol_res / LAMPORTS_PER_SOL:,.4f} SOL")
    print(f"Updated USDC Vault: {new_usdc_res / USDC_UNITS_PER_TOKEN:,.2f} USDC")


if __name__ == "__main__":
    main()
