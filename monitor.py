#!/usr/bin/env python3
"""Real-time trade monitor for Indodax bot."""
import sqlite3
import time
import os

DB = "trades.db"

while True:
    os.system("clear")
    print("=" * 40)
    print("  INDOODAX BOT — PORTFOLIO MONITOR")
    print("=" * 40)

    if not os.path.exists(DB):
        print("  Belum ada data — menunggu cycle pertama...")
    else:
        db = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT 15"
        ).fetchall()]
        stats = dict(db.execute(
            "SELECT status, COUNT(*) as cnt FROM trades GROUP BY status"
        ).fetchall())
        raw = db.execute(
            "SELECT COALESCE(SUM(pnl_idr), 0) FROM trades WHERE status=?",
            ("closed",)
        ).fetchone()
        realized = raw[0] if raw else 0

        open_ = stats.get("open", 0)
        closed = stats.get("closed", 0)
        print(f"  Open: {open_}  |  Closed: {closed}")
        print(f"  Total: {open_ + closed}  |  Realized P&L: {realized:+,} IDR")
        print()

        for r in rows[:10]:
            pnl = r["pnl_idr"] or 0
            pct = r["pnl_pct"] or 0
            print(f"  #{r['id']:>3d} {r['pair']:10s} "
                  f"{r['status']:8s} "
                  f"entry={r['entry_price']:>12,.0f} "
                  f"PnL={pnl:+,} ({pct:+.2f}%)")

        if not rows:
            print("  (belum ada trade)")
        db.close()

    print()
    print("  Refresh 30s | Ctrl+C stop | Ctrl+B d detach")
    time.sleep(30)
