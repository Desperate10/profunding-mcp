"""
Run: python test_venue_matching.py            (pure checks)
     PROFUNDING_API_URL=http://backend:8000/api python test_venue_matching.py --live

Covers the 0.9.20 fixes:
  * venue names from /exchanges are lowercase keys while /opportunities and
    pair intelligence use display names; matching must ignore case
    (analyze_pair's Current Funding / 30-Day Intelligence, compare_exchanges'
    venue filter were permanently empty before);
  * /prices/chart-data points carry `spreadPct`, not `spread_pct`
    (Price Spread Risk and get_price_spread_data were always empty).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from profunding_mcp import server as s  # noqa: E402


def check(name, cond, detail=""):
    print(f"  [{'OK' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        raise AssertionError(name)


def pure():
    print("pure helpers")
    check("same venue ignores case", s._same_venue("hyperliquid", "Hyperliquid"))
    check("different venues differ", not s._same_venue("lighter", "LighterRH"))
    check("non-strings never match", not s._same_venue(None, "Aster"))
    check("spreadPct read", s._spread_pct({"spreadPct": -0.0128}) == -0.0128)
    check("legacy spread_pct still read", s._spread_pct({"spread_pct": 0.5}) == 0.5)
    check("missing spread is None", s._spread_pct({"longPrice": 1.0}) is None)


async def live():
    print("live (dev API)")
    opps = await s.client.get("/opportunities", params={})
    row = next(o for o in opps if "/" in o.get("symbol", ""))
    sym, lx, sx = row["symbol"], row["long_exchange"], row["short_exchange"]
    # Type the venues the way a user would, in lowercase.
    out = await s.analyze_pair(sym, lx.lower(), sx.lower(), 1000)
    funding = out.split("── Current Funding ──", 1)[1].split("──", 1)[0]
    check("analyze_pair finds the live pair from lowercase input",
          "Pair not found" not in funding and "Net APR" in funding, funding.strip()[:160])
    spread = await s.get_price_spread_data(sym, lx.lower(), sx.lower(), 7)
    check("get_price_spread_data reports spreads",
          "no spread calculations" not in spread, spread.strip()[:160])


if __name__ == "__main__":
    pure()
    if "--live" in sys.argv:
        asyncio.run(live())
    print("\nALL PASSED")
