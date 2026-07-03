import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

from .config import CONFIG
from .storage import TradeStore
from .logger import get_logger

log = get_logger()


class DashboardHandler(BaseHTTPRequestHandler):
    store: TradeStore | None = None

    def _json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _html(self, content: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def do_GET(self):
        if self.path == "/":
            self._html(self._render())
        elif self.path == "/api/trades":
            if self.store is None:
                self._json({"error": "store not ready"}, 500)
                return
            trades = self.store.recent_trades(50)
            self._json({"trades": trades})
        elif self.path == "/api/summary":
            if self.store is None:
                self._json({"error": "store not ready"}, 500)
                return
            open_trades = self.store.open_trades()
            total_pnl = self.store.total_pnl()
            base = CONFIG.paper_balance_idr
            balance = base + total_pnl
            daily = self.store.daily_pnl_history(14)
            self._json({
                "open_positions": len(open_trades),
                "total_pnl": total_pnl,
                "balance": balance,
                "daily_pnl": daily,
                "paper_mode": CONFIG.paper_mode,
            })
        else:
            self._json({"error": "not found"}, 404)

    def _render(self) -> str:
        store = self.store
        if store is None:
            return "<html><body><h1>Loading...</h1></body></html>"

        trades = store.recent_trades(20)
        open_trades = store.open_trades()
        total_pnl = store.total_pnl()
        base = CONFIG.paper_balance_idr
        balance = base + total_pnl
        daily = store.daily_pnl_history(14)

        rows = ""
        for t in trades:
            pnl_cls = "green" if (t.get("pnl_pct") or 0) >= 0 else "red"
            rows += f"<tr><td>{t['pair']}</td><td>{t.get('exit_reason', '')}</td>" \
                    f"<td>{t.get('entry_price', 0):,.0f}</td>" \
                    f"<td><span style='color:{pnl_cls}'>{t.get('pnl_pct', 0):+.2%}</span></td>" \
                    f"<td>{t.get('pnl_idr', 0):+,.0f}</td></tr>"

        daily_rows = ""
        for d in daily:
            pnl_cls = "green" if (d.get("pnl_idr") or 0) >= 0 else "red"
            daily_rows += f"<tr><td>{d['day']}</td>" \
                          f"<td><span style='color:{pnl_cls}'>{d['pnl_idr']:+,.0f}</span></td>" \
                          f"<td>{d['trades']}</td></tr>"

        open_rows = ""
        for t in open_trades:
            open_rows += f"<tr><td>{t['pair']}</td><td>{t['entry_price']:,.0f}</td>" \
                         f"<td>{t['size_idr']:,.0f}</td><td>{t.get('entry_time', '')[:19]}</td></tr>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Indodax Bot Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: #0f172a; color: #e2e8f0; padding: 20px; }}
h1 {{ color: #38bdf8; margin-bottom: 20px; }}
h2 {{ color: #94a3b8; margin: 20px 0 10px; }}
.card {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
.stats {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.stat {{ background: #334155; border-radius: 8px; padding: 15px; min-width: 120px; }}
.stat .value {{ font-size: 24px; font-weight: bold; color: #38bdf8; }}
.stat .label {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 2px solid #334155; color: #94a3b8; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
tr:hover td {{ background: #33415533; }}
.green {{ color: #4ade80; }}
.red {{ color: #f87171; }}
.update {{ color: #64748b; font-size: 12px; margin-top: 10px; }}
</style>
</head>
<body>
<h1>🤖 Indodax Bot</h1>
<div class="card">
<div class="stats">
<div class="stat"><div class="value">Rp{balance:,.0f}</div><div class="label">Balance</div></div>
<div class="stat"><div class="value" style="color:{"#4ade80" if total_pnl>=0 else "#f87171"}">{total_pnl:+,.0f}</div><div class="label">Total P&L</div></div>
<div class="stat"><div class="value">{len(open_trades)}</div><div class="label">Open Positions</div></div>
<div class="stat"><div class="value">{len(trades)}</div><div class="label">Closed Trades</div></div>
</div>
<div class="update">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
</div>

<div class="card">
<h2>Open Positions</h2>
{"<table><tr><th>Pair</th><th>Entry</th><th>Size</th><th>Time</th></tr>" + open_rows + "</table>" if open_trades else "<p>No open positions</p>"}
</div>

<div class="card">
<h2>Recent Closed Trades</h2>
<table><tr><th>Pair</th><th>Exit</th><th>Price</th><th>P&L %</th><th>P&L IDR</th></tr>{rows}</table>
</div>

<div class="card">
<h2>Daily P&L (14 days)</h2>
<table><tr><th>Day</th><th>P&L</th><th>Trades</th></tr>{daily_rows}</table>
</div>
</body></html>"""

    def log_message(self, fmt, *args):
        pass


def start_dashboard(store: TradeStore, port: int = 8081):
    DashboardHandler.store = store
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="dashboard")
    t.start()
    log.info("dashboard_started", port=port)
    print(f"  📊 Dashboard: http://localhost:{port}")
    return server
