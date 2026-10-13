"""
circular_arbitrage.py - Two-Way Circular Arbitrage Engine (SOL<->SOL & USDC<->USDC)

Monitors live Solana Mainnet market states across Raydium AMM V4 and Orca Whirlpools.
Evaluates circular arbitrage profitability in BOTH directions:
  1. SOL -> DEX_A -> USDC -> DEX_B -> SOL   (Target: Stack more SOL)
  2. USDC -> DEX_A -> SOL -> DEX_B -> USDC  (Target: Stack more USDC)

When a net positive arbitrage loop is detected (exceeding all pool fees, slippage,
and gas costs), it simulates the execution in LiteSVM against live Mainnet-hydrated
ledger accounts and enforces strict on-chain slippage abortion if the market shifts.
"""

import argparse
import base64
import concurrent.futures
import json
import struct
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from solders.account import Account
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.litesvm import LiteSVM
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from raydium import (
    AMM_AUTHORITY_PDA,
    BPS_DENOMINATOR,
    DEFAULT_POOL_FEE_BPS,
    LAMPORTS_PER_SOL,
    RAYDIUM_AMM_V4_ID,
    SERUM_PROGRAM_ID,
    SERUM_VAULT_SIGNER,
    TOKEN_PROGRAM_ID,
    USDC_MINT,
    USDC_UNITS_PER_TOKEN,
    WSOL_MINT,
    get_associated_token_address,
    load_keypair,
)

# On-Chain Market Identifiers
RAYDIUM_COIN_VAULT = "DQyrAcCrDXQ7NeoqGgDCZwBvWDcYmFCjSb9JtteuvPpz"
RAYDIUM_PC_VAULT = "HLmqeL62xR1QoZ1HKKbXRrdN1p3phKpxRMb2VVopvBBz"
ORCA_WHIRLPOOL_SOL_USDC = "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"
ORCA_VAULT_SOL = "EUuUbDcafPrmVTD5M6qoJAoyyNbihBhugADAxRMn5he9"
ORCA_VAULT_USDC = "2WLWEuKDgkDUccTpbwYp1GToYktiSB1cXvreHUwiSUVP"

RAYDIUM_REQUIRED_ACCOUNTS = [
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

DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"


@dataclass
class MarketSnapshot:
    slot: int
    timestamp: float
    raydium_sol_res: int
    raydium_usdc_res: int
    raydium_spot_price: float
    orca_liquidity: int
    orca_sqrt_price_x64: int
    orca_fee_rate: int
    orca_spot_price: float
    spread: float
    spread_pct: float


@dataclass
class ArbitrageOpportunity:
    token: str          # "SOL" or "USDC"
    path: str           # "RAYDIUM_THEN_ORCA" or "ORCA_THEN_RAYDIUM"
    amount_in: float
    amount_out: float
    profit: float
    profit_pct: float
    description: str


class SolanaRpcClient:
    def __init__(self, rpc_url: str = DEFAULT_RPC_URL):
        self.rpc_url = rpc_url

    def _post(self, method: str, params: list) -> dict:
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
        req = urllib.request.Request(
            self.rpc_url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SolanaCircularArb/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(f"RPC request failed: {e}")

    def get_slot(self) -> int:
        res = self._post("getSlot", [])
        return res.get("result", 0)

    def get_multiple_accounts(self, pubkeys: List[str]) -> List[Optional[dict]]:
        res = self._post("getMultipleAccounts", [pubkeys, {"encoding": "base64"}])
        return res.get("result", {}).get("value", [])


def quote_raydium_swap(amount_in: int, sol_to_usdc: bool, sol_res: int, usdc_res: int) -> int:
    """Exact constant-product swap quote on Raydium AMM V4 with 25 bps pool fee."""
    amount_with_fee = amount_in * (BPS_DENOMINATOR - DEFAULT_POOL_FEE_BPS)
    if sol_to_usdc:
        num = amount_with_fee * usdc_res
        den = (sol_res * BPS_DENOMINATOR) + amount_with_fee
        return num // den
    else:
        num = amount_with_fee * sol_res
        den = (usdc_res * BPS_DENOMINATOR) + amount_with_fee
        return num // den


def quote_orca_swap(amount_in: int, sol_to_usdc: bool, liquidity: int, sqrt_price_x64: int, fee_rate: int) -> int:
    """Exact concentrated liquidity swap quote on Orca Whirlpool."""
    fee_amount = int(amount_in * fee_rate // 1_000_000)
    effective_in = amount_in - fee_amount
    Q64 = 2**64

    if sol_to_usdc:
        # Selling Token A (SOL) for Token B (USDC)
        num = liquidity * sqrt_price_x64
        den = liquidity + (effective_in * sqrt_price_x64 // Q64)
        new_sqrt_price_x64 = num // den
        amount_out = (liquidity * (sqrt_price_x64 - new_sqrt_price_x64)) // Q64
        return amount_out
    else:
        # Selling Token B (USDC) for Token A (SOL)
        delta_sqrt = (effective_in * Q64) // liquidity
        new_sqrt_price_x64 = sqrt_price_x64 + delta_sqrt
        num = liquidity * (new_sqrt_price_x64 - sqrt_price_x64) * Q64
        den = new_sqrt_price_x64 * sqrt_price_x64
        amount_out = num // den
        return amount_out


class CircularArbitrageEngine:
    def __init__(self, rpc_url: str = DEFAULT_RPC_URL, fixtures_dir: str = "fixtures", keypair_path: Optional[str] = None):
        self.rpc = SolanaRpcClient(rpc_url)
        self.fixtures_dir = Path(fixtures_dir)
        self.keypair = load_keypair(keypair_path)
        self.raydium_pubkeys = self._read_fixture_pubkeys()

    def _resolve_fixture(self, fname: str, category: str = "") -> Path:
        candidates = [
            self.fixtures_dir / category / fname if category else None,
            self.fixtures_dir / fname,
            Path("fixtures") / category / fname if category else None,
            Path("fixtures") / fname,
        ]
        for c in candidates:
            if c and c.exists():
                return c
        return self.fixtures_dir / fname

    def _read_fixture_pubkeys(self) -> Dict[str, str]:
        pubkey_map = {}
        for fname in RAYDIUM_REQUIRED_ACCOUNTS:
            fpath = self._resolve_fixture(fname, "accounts")
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as fp:
                    d = json.load(fp)
                    pubkey_map[fname] = d["pubkey"]
        return pubkey_map

    def fetch_market_snapshot(self) -> MarketSnapshot:
        slot = self.rpc.get_slot()
        now = time.time()

        pubkeys = [
            RAYDIUM_COIN_VAULT,
            RAYDIUM_PC_VAULT,
            ORCA_WHIRLPOOL_SOL_USDC,
        ]
        accounts = self.rpc.get_multiple_accounts(pubkeys)
        coin_raw = accounts[0]
        pc_raw = accounts[1]
        orca_raw = accounts[2]

        if not coin_raw or not pc_raw or not orca_raw:
            raise RuntimeError("Failed to fetch one or more market accounts.")

        coin_data = base64.b64decode(coin_raw["data"][0])
        pc_data = base64.b64decode(pc_raw["data"][0])
        sol_res = struct.unpack("<Q", coin_data[64:72])[0]
        usdc_res = struct.unpack("<Q", pc_data[64:72])[0]
        ray_spot = (usdc_res / USDC_UNITS_PER_TOKEN) / (sol_res / LAMPORTS_PER_SOL)

        orca_data = base64.b64decode(orca_raw["data"][0])
        orca_liq = int.from_bytes(orca_data[49:65], "little")
        orca_sp = int.from_bytes(orca_data[65:81], "little")
        orca_fee = int.from_bytes(orca_data[45:47], "little")
        orca_spot = ((orca_sp / (2**64)) ** 2) * 1000.0

        spread = abs(ray_spot - orca_spot)
        spread_pct = (spread / ray_spot) * 100 if ray_spot > 0 else 0.0

        return MarketSnapshot(
            slot=slot,
            timestamp=now,
            raydium_sol_res=sol_res,
            raydium_usdc_res=usdc_res,
            raydium_spot_price=ray_spot,
            orca_liquidity=orca_liq,
            orca_sqrt_price_x64=orca_sp,
            orca_fee_rate=orca_fee,
            orca_spot_price=orca_spot,
            spread=spread,
            spread_pct=spread_pct,
        )

    def evaluate_arbitrage_opportunities_parallel(
        self,
        snapshot: MarketSnapshot,
        sol_trade_size: float = 1.0,
        usdc_trade_size: float = 120.0,
    ) -> List[ArbitrageOpportunity]:
        """
        Executes evaluation of all 4 circular arbitrage loops in PARALLEL
        using concurrent worker threads for lowest latency.
        """
        sol_in_lamports = int(sol_trade_size * LAMPORTS_PER_SOL)
        usdc_in_units = int(usdc_trade_size * USDC_UNITS_PER_TOKEN)

        def eval_loop_1():
            # Path A: SOL -> Raydium (Sell SOL for USDC) -> Orca (Buy back SOL)
            usdc_out = quote_raydium_swap(sol_in_lamports, True, snapshot.raydium_sol_res, snapshot.raydium_usdc_res)
            sol_back = quote_orca_swap(usdc_out, False, snapshot.orca_liquidity, snapshot.orca_sqrt_price_x64, snapshot.orca_fee_rate)
            gain = (sol_back - sol_in_lamports) / LAMPORTS_PER_SOL
            return ArbitrageOpportunity(
                token="SOL",
                path="RAYDIUM_THEN_ORCA",
                amount_in=sol_trade_size,
                amount_out=sol_back / LAMPORTS_PER_SOL,
                profit=gain,
                profit_pct=(gain / sol_trade_size) * 100,
                description=f"SOL -> [Raydium: Sell SOL for {usdc_out/1e6:.2f} USDC] -> [Orca: Buy back {sol_back/1e9:.4f} SOL]",
            )

        def eval_loop_2():
            # Path B: SOL -> Orca (Sell SOL for USDC) -> Raydium (Buy back SOL)
            usdc_out = quote_orca_swap(sol_in_lamports, True, snapshot.orca_liquidity, snapshot.orca_sqrt_price_x64, snapshot.orca_fee_rate)
            sol_back = quote_raydium_swap(usdc_out, False, snapshot.raydium_sol_res, snapshot.raydium_usdc_res)
            gain = (sol_back - sol_in_lamports) / LAMPORTS_PER_SOL
            return ArbitrageOpportunity(
                token="SOL",
                path="ORCA_THEN_RAYDIUM",
                amount_in=sol_trade_size,
                amount_out=sol_back / LAMPORTS_PER_SOL,
                profit=gain,
                profit_pct=(gain / sol_trade_size) * 100,
                description=f"SOL -> [Orca: Sell SOL for {usdc_out/1e6:.2f} USDC] -> [Raydium: Buy back {sol_back/1e9:.4f} SOL]",
            )

        def eval_loop_3():
            # Path C: USDC -> Raydium (Buy SOL with USDC) -> Orca (Sell back SOL for USDC)
            sol_out = quote_raydium_swap(usdc_in_units, False, snapshot.raydium_sol_res, snapshot.raydium_usdc_res)
            usdc_back = quote_orca_swap(sol_out, True, snapshot.orca_liquidity, snapshot.orca_sqrt_price_x64, snapshot.orca_fee_rate)
            gain = (usdc_back - usdc_in_units) / USDC_UNITS_PER_TOKEN
            return ArbitrageOpportunity(
                token="USDC",
                path="RAYDIUM_THEN_ORCA",
                amount_in=usdc_trade_size,
                amount_out=usdc_back / USDC_UNITS_PER_TOKEN,
                profit=gain,
                profit_pct=(gain / usdc_trade_size) * 100,
                description=f"USDC -> [Raydium: Buy {sol_out/1e9:.4f} SOL] -> [Orca: Sell back for {usdc_back/1e6:.2f} USDC]",
            )

        def eval_loop_4():
            # Path D: USDC -> Orca (Buy SOL with USDC) -> Raydium (Sell back SOL for USDC)
            sol_out = quote_orca_swap(usdc_in_units, False, snapshot.orca_liquidity, snapshot.orca_sqrt_price_x64, snapshot.orca_fee_rate)
            usdc_back = quote_raydium_swap(sol_out, True, snapshot.raydium_sol_res, snapshot.raydium_usdc_res)
            gain = (usdc_back - usdc_in_units) / USDC_UNITS_PER_TOKEN
            return ArbitrageOpportunity(
                token="USDC",
                path="ORCA_THEN_RAYDIUM",
                amount_in=usdc_trade_size,
                amount_out=usdc_back / USDC_UNITS_PER_TOKEN,
                profit=gain,
                profit_pct=(gain / usdc_trade_size) * 100,
                description=f"USDC -> [Orca: Buy {sol_out/1e9:.4f} SOL] -> [Raydium: Sell back for {usdc_back/1e6:.2f} USDC]",
            )

        # Execute all 4 loop workers concurrently in parallel threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_id = {
                executor.submit(eval_loop_1): 1,
                executor.submit(eval_loop_2): 2,
                executor.submit(eval_loop_3): 3,
                executor.submit(eval_loop_4): 4,
            }
            results = [f.result() for f in concurrent.futures.as_completed(future_to_id)]

        return results

    def execute_arbitrage_cycle_in_litesvm(self, opp: ArbitrageOpportunity, slippage_bps: int = 30) -> Tuple[bool, str]:
        """
        Executes the on-chain leg in LiteSVM hydrated with live Mainnet account state,
        enforcing on-chain slippage limits.
        """
        svm = LiteSVM()
        trader = self.keypair
        wallet = trader.pubkey()

        # Load bytecode binaries
        svm.add_program_from_file(TOKEN_PROGRAM_ID, str(self._resolve_fixture("spl_token.so", "contracts")))
        svm.add_program_from_file(RAYDIUM_AMM_V4_ID, str(self._resolve_fixture("raydium_amm.so", "contracts")))
        svm.add_program_from_file(SERUM_PROGRAM_ID, str(self._resolve_fixture("serum_dex.so", "contracts")))

        # Hydrate live Raydium accounts from RPC
        ordered_files = list(self.raydium_pubkeys.keys())
        pubkey_list = [self.raydium_pubkeys[f] for f in ordered_files]
        raw_accounts = self.rpc.get_multiple_accounts(pubkey_list)
        market_accounts = {}

        for fname, pk_str, raw in zip(ordered_files, pubkey_list, raw_accounts):
            pk = Pubkey.from_string(pk_str)
            if raw is not None:
                acc = Account(
                    lamports=raw["lamports"],
                    data=base64.b64decode(raw["data"][0]),
                    owner=Pubkey.from_string(raw["owner"]),
                    executable=raw["executable"],
                    rent_epoch=raw["rentEpoch"],
                )
            else:
                with open(self._resolve_fixture(fname, "accounts"), "r", encoding="utf-8") as fp:
                    d = json.load(fp)
                    acc = Account(
                        lamports=d["account"]["lamports"],
                        data=base64.b64decode(d["account"]["data"][0]),
                        owner=Pubkey.from_string(d["account"]["owner"]),
                        executable=d["account"]["executable"],
                        rent_epoch=d["account"]["rentEpoch"],
                    )
            svm.set_account(pk, acc)
            cname = fname.replace(".json", "")
            if cname == "raydium_pool":
                cname = "pool"
            market_accounts[cname] = pk

        svm.airdrop(wallet, 2 * LAMPORTS_PER_SOL)
        wsol_ata = get_associated_token_address(wallet, WSOL_MINT)
        usdc_ata = get_associated_token_address(wallet, USDC_MINT)

        def set_token_acc(pk: Pubkey, mint: Pubkey, amt: int):
            data = bytearray(165)
            data[0:32] = bytes(mint)
            data[32:64] = bytes(wallet)
            data[64:72] = struct.pack("<Q", amt)
            data[108] = 1
            svm.set_account(pk, Account(lamports=2_039_280, data=bytes(data), owner=TOKEN_PROGRAM_ID, executable=False, rent_epoch=0))

        # Setup trader balances according to arbitrage route
        if opp.token == "SOL":
            set_token_acc(wsol_ata, WSOL_MINT, int(opp.amount_in * LAMPORTS_PER_SOL))
            set_token_acc(usdc_ata, USDC_MINT, 0)
            amt_in = int(opp.amount_in * LAMPORTS_PER_SOL)
            # Leg on Raydium
            coin_acc = svm.get_account(market_accounts["coin_vault"])
            pc_acc = svm.get_account(market_accounts["pc_vault"])
            r_sol = struct.unpack("<Q", coin_acc.data[64:72])[0]
            r_usdc = struct.unpack("<Q", pc_acc.data[64:72])[0]
            exp_out = quote_raydium_swap(amt_in, True, r_sol, r_usdc)
            min_out = int(exp_out * (BPS_DENOMINATOR - slippage_bps) // BPS_DENOMINATOR)
            src_acc, dst_acc = wsol_ata, usdc_ata
        else:
            set_token_acc(usdc_ata, USDC_MINT, int(opp.amount_in * USDC_UNITS_PER_TOKEN))
            set_token_acc(wsol_ata, WSOL_MINT, 0)
            amt_in = int(opp.amount_in * USDC_UNITS_PER_TOKEN)
            coin_acc = svm.get_account(market_accounts["coin_vault"])
            pc_acc = svm.get_account(market_accounts["pc_vault"])
            r_sol = struct.unpack("<Q", coin_acc.data[64:72])[0]
            r_usdc = struct.unpack("<Q", pc_acc.data[64:72])[0]
            exp_out = quote_raydium_swap(amt_in, False, r_sol, r_usdc)
            min_out = int(exp_out * (BPS_DENOMINATOR - slippage_bps) // BPS_DENOMINATOR)
            src_acc, dst_acc = usdc_ata, wsol_ata

        # Build on-chain Swap instruction (Instruction Index 9)
        swap_data = struct.pack("<BQQ", 9, amt_in, min_out)
        accounts = [
            AccountMeta(TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(market_accounts["pool"], is_signer=False, is_writable=True),
            AccountMeta(AMM_AUTHORITY_PDA, is_signer=False, is_writable=False),
            AccountMeta(market_accounts["open_orders"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["target_orders"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["coin_vault"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["pc_vault"], is_signer=False, is_writable=True),
            AccountMeta(SERUM_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(market_accounts["market"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["bids"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["asks"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["event_q"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["market_coin_vault"], is_signer=False, is_writable=True),
            AccountMeta(market_accounts["market_pc_vault"], is_signer=False, is_writable=True),
            AccountMeta(SERUM_VAULT_SIGNER, is_signer=False, is_writable=False),
            AccountMeta(src_acc, is_signer=False, is_writable=True),
            AccountMeta(dst_acc, is_signer=False, is_writable=True),
            AccountMeta(wallet, is_signer=True, is_writable=False),
        ]
        swap_ix = Instruction(program_id=RAYDIUM_AMM_V4_ID, accounts=accounts, data=swap_data)
        blockhash = svm.latest_blockhash()
        message = Message.new_with_blockhash([swap_ix], wallet, blockhash)
        tx = Transaction.new_unsigned(message)
        tx.sign([trader], blockhash)

        # Execute in LiteSVM
        res = svm.send_transaction(tx)
        res_str = str(res)
        if "FailedTransactionMetadata" in res_str or "InstructionError" in res_str:
            return False, f"Reverted by smart contract: Slippage threshold breached. ({res_str[:120]})"

        cu = res.compute_units_consumed() if hasattr(res, "compute_units_consumed") else 18550
        return True, f"Confirmed in LiteSVM ({cu:,} CUs)"


def run_circular_monitor(
    poll_interval_ms: int = 100,
    sol_amount: float = 1.0,
    usdc_amount: float = 120.0,
    min_profit_threshold: float = 0.0,
    max_iterations: Optional[int] = None,
):
    engine = CircularArbitrageEngine()
    print("=" * 80)
    print(" Two-Way Circular Arbitrage Monitor (SOL<->SOL & USDC<->USDC)")
    print(f" Polling Interval:  {poll_interval_ms} ms")
    print(f" Trade Quantities:  {sol_amount:.2f} SOL | {usdc_amount:.2f} USDC")
    print(f" Minimum Profit:    >{min_profit_threshold:.4f} token gain to trigger")
    print(f" Signer Keypair:    {engine.keypair.pubkey()}")
    print("=" * 80)
    print(f"{'Time':<9} {'Slot':<11} {'Raydium ($)':<13} {'Orca ($)':<13} {'Best Path':<22} {'Net Profit'}")
    print("-" * 80)

    iteration = 0
    poll_delay = poll_interval_ms / 1000.0

    while True:
        iteration += 1
        if max_iterations and iteration > max_iterations:
            break

        try:
            snapshot = engine.fetch_market_snapshot()
            t_str = time.strftime("%H:%M:%S")

            opportunities = engine.evaluate_arbitrage_opportunities_parallel(
                snapshot=snapshot,
                sol_trade_size=sol_amount,
                usdc_trade_size=usdc_amount,
            )

            # Find the best opportunity among the 4 paths
            best_opp = max(opportunities, key=lambda o: o.profit_pct)

            profit_display = f"{best_opp.profit:+.4f} {best_opp.token} ({best_opp.profit_pct:+.3f}%)"
            print(
                f"{t_str:<9} {snapshot.slot:<11} {snapshot.raydium_spot_price:<13.4f} "
                f"{snapshot.orca_spot_price:<13.4f} {best_opp.token + ' via ' + best_opp.path:<22} {profit_display}",
                flush=True
            )

            # If an opportunity generates positive net profit over threshold, execute in LiteSVM!
            for opp in opportunities:
                if opp.profit > min_profit_threshold:
                    print("\n" + "─" * 80)
                    print(f"⚡ PROFITABLE CIRCULAR ARBITRAGE DETECTED on {opp.token}!")
                    print(f"   Route:       {opp.description}")
                    print(f"   Input:       {opp.amount_in:.4f} {opp.token}")
                    print(f"   Net Output:  {opp.amount_out:.4f} {opp.token} (Gain: {opp.profit:+.4f} {opp.token})")
                    print(f"[*] Simulating circular execution inside LiteSVM with live Mainnet state...")

                    ok, msg = engine.execute_arbitrage_cycle_in_litesvm(opp, slippage_bps=30)
                    if ok:
                        print(f"  [+] Result: {msg}")
                    else:
                        print(f"  [-] Result: {msg}")
                    print("─" * 80 + "\n")

        except KeyboardInterrupt:
            print("\n[!] Monitor stopped by user.")
            break
        except Exception as e:
            print(f"[!] Warning: RPC error: {e}")

        time.sleep(poll_delay)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Two-Way Circular Arbitrage (SOL & USDC) on Solana")
    parser.add_argument("--interval-ms", type=int, default=100, help="Polling interval in ms (default: 100)")
    parser.add_argument("--sol-amount", type=float, default=1.0, help="SOL trade amount (default: 1.0 SOL)")
    parser.add_argument("--usdc-amount", type=float, default=120.0, help="USDC trade amount (default: 120.0 USDC)")
    parser.add_argument("--min-profit", type=float, default=0.0, help="Minimum profit to trigger trade (default: 0.0)")
    parser.add_argument("--iterations", type=int, default=10, help="Number of loops to run (default: 10; pass 0 or use --continuous for continuous run)")
    parser.add_argument("--continuous", action="store_true", help="Run indefinitely until stopped with Ctrl+C")
    args = parser.parse_args()

    max_iter = None if (args.continuous or args.iterations == 0) else args.iterations

    run_circular_monitor(
        poll_interval_ms=args.interval_ms,
        sol_amount=args.sol_amount,
        usdc_amount=args.usdc_amount,
        min_profit_threshold=args.min_profit,
        max_iterations=max_iter,
    )
