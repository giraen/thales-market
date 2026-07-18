import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.ledger.service import get_position
from app.market.service import get_market_snapshot, MarketDataUnavailable, InsufficientHistory
from app.market.lib.strategies import check_buy_signals, check_sell_signals
from app.core.database import get_db

PEG_CACHE_MAX_AGE = timedelta(hours=24)

def run_scan():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, ticker,
               last_buy_decision, last_sell_decision,
               cached_peg_ratio, peg_fetched_at
        FROM watchlist
        ORDER BY ticker
    """)
    rows = cursor.fetchall()

    snapshot_cache = {}
    scanned, changed, errored = 0, 0, 0

    for row in rows:
        ticker, user_id = row['ticker'], row['user_id']

        try:
            if ticker not in snapshot_cache:
                peg_is_fresh = (
                    row['peg_fetched_at'] is not None
                    and datetime.now(timezone.utc) - row['peg_fetched_at'] < PEG_CACHE_MAX_AGE
                )
                cached_peg = float(row['cached_peg_ratio']) if peg_is_fresh and row['cached_peg_ratio'] else None

                df, resolved_peg = get_market_snapshot(ticker, cached_peg=cached_peg)
                snapshot_cache[ticker] = {"df": df, "peg": resolved_peg, "needs_peg_save": not peg_is_fresh}

            snap = snapshot_cache[ticker]
            df, peg_ratio = snap["df"], snap["peg"]

            if snap["needs_peg_save"]:
                cursor.execute("""
                    UPDATE watchlist SET cached_peg_ratio = %s, peg_fetched_at = %s WHERE ticker = %s
                """, (peg_ratio, datetime.now(timezone.utc), ticker))
                snap["needs_peg_save"] = False  # only write once per ticker per run

            # Buy-check always runs
            buy_result = check_buy_signals(df, peg_ratio)
            if buy_result['decision'] != row['last_buy_decision']:
                print(f"[CHANGED] {user_id} | {ticker} BUY: {row['last_buy_decision']} -> {buy_result['decision']}")
                cursor.execute("""
                    UPDATE watchlist SET last_buy_decision = %s, last_buy_notified_at = %s WHERE id = %s
                """, (buy_result['decision'], datetime.now(timezone.utc), row['id']))
                changed += 1

            # Sell-check only if currently held
            position = get_position(conn, user_id, ticker)
            if position["net_quantity"] > 0:
                sell_result = check_sell_signals(df, float(position["avg_entry_price"]))
                if sell_result['decision'] != row['last_sell_decision']:
                    print(f"[CHANGED] {user_id} | {ticker} SELL: {row['last_sell_decision']} -> {sell_result['decision']}")
                    cursor.execute("""
                        UPDATE watchlist SET last_sell_decision = %s, last_sell_notified_at = %s WHERE id = %s
                    """, (sell_result['decision'], datetime.now(timezone.utc), row['id']))
                    changed += 1

            scanned += 1

        except (MarketDataUnavailable, InsufficientHistory) as e:
            print(f"[SKIPPED] {ticker}: {e}")
            errored += 1
        except Exception as e:
            print(f"[ERROR] {ticker} for {user_id}: {e}")
            errored += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\nScan complete. {scanned} checks run, {changed} signals changed, {errored} errors.")


if __name__ == "__main__":
    run_scan()