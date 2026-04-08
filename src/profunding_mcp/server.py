"""ProFunding MCP Server — funding rate arbitrage tools for AI assistants."""

from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from .client import client


@asynccontextmanager
async def _lifespan(server):
    """Validate API key on startup."""
    try:
        info = await client.validate_key()
        tier = info.get("tier", "free")
    except Exception:
        tier = "free"
    yield
    await client.close()


mcp = FastMCP(
    "ProFunding",
    instructions="Live funding rate arbitrage data across 20+ perpetual DEXes. "
    "Find delta-neutral trading opportunities, run backtests, and get deep analytics.",
    lifespan=_lifespan,
)


# ─── Helpers ──────────────────────────────────────────────────

async def _ensure_validated():
    """Lazy-validate the API key if not done yet."""
    if client._tier is None:
        try:
            await client.validate_key()
        except Exception:
            client._tier = "free"


async def _require_paid():
    """Raise if the API key doesn't have paid tier."""
    await _ensure_validated()
    if not client.is_paid():
        raise ValueError(
            "This tool requires a paid ProFunding API key. "
            "Visit profunding.pro to upgrade."
        )


# Canonical exchange names (lowercase → display)
_EXCHANGE_NAMES: dict[str, str] | None = None


async def _get_exchange_map() -> dict[str, str]:
    """Build lowercase → canonical name map from the API."""
    global _EXCHANGE_NAMES
    if _EXCHANGE_NAMES is not None:
        return _EXCHANGE_NAMES
    try:
        data = await client.get("/exchanges")
        _EXCHANGE_NAMES = {
            ex["name"].lower(): ex["name"]
            for ex in data.get("exchanges", [])
        }
    except Exception:
        _EXCHANGE_NAMES = {}
    return _EXCHANGE_NAMES


async def _normalize_exchange(name: str) -> str:
    """Resolve user input to canonical exchange name (case-insensitive)."""
    mapping = await _get_exchange_map()
    canonical = mapping.get(name.lower())
    return canonical if canonical else name


def _fmt_opp(o: dict) -> str:
    """Format a single opportunity for display."""
    line = (
        f"  {o['symbol']} — Long {o['long_exchange']} ({o['long_apr']:+.1f}%) / "
        f"Short {o['short_exchange']} ({o['short_apr']:+.1f}%) — "
        f"Net {o['net_apr']:.1f}% APR, breakeven {o.get('breakeven_days', '?')} days"
    )
    # Add liquidity info if available
    tags = []
    long_spread = o.get('long_spread_pct')
    short_spread = o.get('short_spread_pct')
    if long_spread is not None or short_spread is not None:
        worst_spread = max(long_spread or 0, short_spread or 0)
        tags.append(f"spread {worst_spread:.2f}%")
    long_vol = o.get('long_volume_24h')
    short_vol = o.get('short_volume_24h')
    if long_vol is not None or short_vol is not None:
        min_volume = min(long_vol or float('inf'), short_vol or float('inf'))
        if min_volume < float('inf'):
            tags.append(f"vol ${min_volume:,.0f}")
    if o.get('pre_tge'):
        tags.append("pre-TGE")
    if tags:
        line += f" [{', '.join(tags)}]"
    return line


# ─── FREE TIER TOOLS ─────────────────────────────────────────

@mcp.tool()
async def get_opportunities(
    min_apr: float = 0,
    symbol: str = "",
    exchange: str = "",
    limit: int = 20,
    pre_tge_only: bool = False,
) -> str:
    """Get live funding rate arbitrage opportunities across all DEXes.
    [Free]

    Args:
        min_apr: Minimum net APR to filter (default 0)
        symbol: Filter by trading pair (e.g. "ETH/USDC")
        exchange: Filter by exchange name (e.g. "Hyperliquid")
        limit: Max number of results (default 20)
        pre_tge_only: Only show opportunities where at least one DEX is pre-token (points farming)
    """
    if exchange:
        exchange = await _normalize_exchange(exchange)
    params = {}
    if min_apr > 0:
        params["min_apr"] = min_apr
    if symbol:
        params["symbol"] = symbol

    data = await client.get("/opportunities", params=params)

    if exchange:
        exchange_lower = exchange.lower()
        data = [opp for opp in data if exchange_lower in opp["long_exchange"].lower() or exchange_lower in opp["short_exchange"].lower()]

    if pre_tge_only:
        data = [opp for opp in data if opp.get("pre_tge")]

    data = sorted(data, key=lambda opp: opp["net_apr"], reverse=True)[:limit]

    if not data:
        return "No opportunities found matching your criteria."

    lines = [f"Found {len(data)} opportunities:\n"]
    for o in data:
        lines.append(_fmt_opp(o))

    return "\n".join(lines)


@mcp.tool()
async def get_exchanges() -> str:
    """List all connected DEXes with their status and funding interval.
    [Free]
    """
    data = await client.get("/exchanges")
    exchanges = data.get("exchanges", [])

    if not exchanges:
        return "No exchanges connected."

    lines = [f"{len(exchanges)} exchanges connected:\n"]
    for ex in exchanges:
        status = "online" if ex["connected"] else "offline"
        lines.append(f"  {ex['name']} — {status}, {ex['funding_interval_hours']}h funding interval")

    return "\n".join(lines)


@mcp.tool()
async def get_historical_rates(
    symbol: str,
    exchange: str,
    days: int = 7,
) -> str:
    """Get historical funding rates for a symbol on a specific exchange.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        exchange: Exchange name (e.g. "Hyperliquid")
        days: Lookback period in days (1-90, default 7)
    """
    exchange = await _normalize_exchange(exchange)
    data = await client.get("/rates/historical", params={
        "symbol": symbol,
        "exchange": exchange,
        "days": days,
    })

    rates = data if isinstance(data, list) else data.get("rates", [])

    if not rates:
        return f"No historical data for {symbol} on {exchange} (last {days} days)."

    # Summarize
    aprs = [float(r.get("funding_rate_apr", 0)) for r in rates]
    avg = sum(aprs) / len(aprs) if aprs else 0
    mn, mx = min(aprs), max(aprs)

    return (
        f"{symbol} on {exchange} — last {days} days ({len(rates)} data points):\n"
        f"  Avg APR: {avg:.1f}%\n"
        f"  Min APR: {mn:.1f}%\n"
        f"  Max APR: {mx:.1f}%"
    )


@mcp.tool()
async def run_backtest(
    symbol: str,
    long_exchange: str,
    short_exchange: str,
    position_size: float = 1000,
    days: int = 7,
) -> str:
    """Backtest a delta-neutral funding arbitrage trade with historical data.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: Exchange to go long on
        short_exchange: Exchange to go short on
        position_size: Position size in USD (default 1000)
        days: Backtest period in days (1-90, default 7)
    """
    long_exchange = await _normalize_exchange(long_exchange)
    short_exchange = await _normalize_exchange(short_exchange)
    data = await client.post("/backtest", json={
        "symbol": symbol,
        "long_exchange": long_exchange,
        "short_exchange": short_exchange,
        "position_size": position_size,
        "days": days,
        "execution_fee_bps": 10,
    })

    pnl = data.get("total_pnl", 0)
    pnl_pct = data.get("pnl_percentage", 0)
    funding = data.get("total_funding_received", 0)
    fees = data.get("total_fees_paid", 0)
    sharpe = data.get("sharpe_ratio", 0)

    result = (
        f"Backtest: {symbol} — Long {long_exchange} / Short {short_exchange}\n"
        f"  Period: {days} days, Position: ${position_size:,.0f}\n"
        f"  Total PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
        f"  Funding received: ${funding:,.2f}\n"
        f"  Fees paid: ${fees:,.2f}\n"
        f"  Sharpe ratio: {sharpe:.2f}"
    )

    if data.get("has_price_data") and data.get("total_pnl_with_spread") is not None:
        spread_pnl = data.get("spread_pnl", 0)
        total_with_spread = data["total_pnl_with_spread"]
        result += (
            f"\n  Price spread PnL: ${spread_pnl:,.2f}"
            f"\n  Total PnL (with spread): ${total_with_spread:,.2f}"
        )

    hist_slip = data.get("historical_slippage_bps")
    if hist_slip is not None:
        result += f"\n  Historical bid-ask slippage: {hist_slip:.1f} bps"

    return result


@mcp.tool()
async def get_rate_chart_data(
    symbol: str,
    long_exchange: str,
    short_exchange: str,
    days: int = 30,
) -> str:
    """Get funding rate spread chart data for a pair across two exchanges.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: First exchange
        short_exchange: Second exchange
        days: Lookback period (1-90, default 30)
    """
    long_exchange = await _normalize_exchange(long_exchange)
    short_exchange = await _normalize_exchange(short_exchange)
    data = await client.get("/rates/chart-data", params={
        "symbol": symbol,
        "long_exchange": long_exchange,
        "short_exchange": short_exchange,
        "days": days,
    })

    points = data if isinstance(data, list) else data.get("data", [])

    if not points:
        return f"No chart data for {symbol} ({long_exchange} vs {short_exchange})."

    # Compute spread statistics
    spreads = []
    for p in points:
        long_apr = p.get("long_apr", 0) or 0
        short_apr = p.get("short_apr", 0) or 0
        spreads.append(short_apr - long_apr)

    avg_spread = sum(spreads) / len(spreads) if spreads else 0
    max_spread = max(spreads) if spreads else 0
    min_spread = min(spreads) if spreads else 0

    return (
        f"{symbol} spread ({long_exchange} vs {short_exchange}) — last {days} days:\n"
        f"  Data points: {len(points)}\n"
        f"  Avg spread: {avg_spread:.1f}% APR\n"
        f"  Max spread: {max_spread:.1f}% APR\n"
        f"  Min spread: {min_spread:.1f}% APR"
    )


# ─── PAID TIER TOOLS ─────────────────────────────────────────

@mcp.tool()
async def get_pair_intelligence() -> str:
    """Get risk scores and backtested APR for all opportunity pairs.
    Pre-computed every 5 minutes. Includes spread risk, 30d average, smart ranking.
    [Free]
    """
    data = await client.get("/analytics/pair-intelligence")

    pairs = data.get("pairs", {})
    if not pairs:
        return "No pair intelligence data available."

    lines = [f"Pair intelligence ({len(pairs)} pairs, {data.get('days', 30)}d window):\n"]

    # Sort by smart score (combines APR, stability, liquidity, depth)
    sorted_pairs = sorted(pairs.items(), key=lambda x: x[1].get("smart_score", 0), reverse=True)

    for pair_key, info in sorted_pairs[:15]:
        bt_apr = info.get("backtested_net_apr", info.get("backtested_apr", 0))
        score = info.get("smart_score", 0)
        stability = info.get("stability_pct", 0)
        risk = info.get("risk_level", "?")
        depth = info.get("depth_score")
        days = info.get("data_days", 0)

        depth_label = {1.0: "$10k+", 0.8: "$5-10k", 0.5: "$1-5k", 0.2: "<$1k"}.get(depth, "?")
        lines.append(
            f"  {pair_key} — score {score:.1f}, bt {bt_apr:.1f}% APR, "
            f"stability {stability:.0f}%, depth {depth_label}, risk {risk}, {days:.0f}d data"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_price_spread_data(
    symbol: str,
    long_exchange: str,
    short_exchange: str,
    days: int = 7,
) -> str:
    """Get hourly mark prices and spread between two exchanges for price risk analysis.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: First exchange
        short_exchange: Second exchange
        days: Lookback period (1-30, default 7)
    """
    long_exchange = await _normalize_exchange(long_exchange)
    short_exchange = await _normalize_exchange(short_exchange)
    data = await client.get("/prices/chart-data", params={
        "symbol": symbol,
        "long_exchange": long_exchange,
        "short_exchange": short_exchange,
        "days": days,
    })

    points = data if isinstance(data, list) else data.get("data", [])
    if not points:
        return f"No price data for {symbol} ({long_exchange} vs {short_exchange})."

    spreads = [p.get("spread_pct", 0) for p in points if p.get("spread_pct") is not None]
    if not spreads:
        return "Price data available but no spread calculations."

    avg = sum(spreads) / len(spreads)
    mx = max(spreads)
    high_hours = sum(1 for s in spreads if s > 0.5)

    return (
        f"{symbol} price spread ({long_exchange} vs {short_exchange}) — last {days} days:\n"
        f"  Data points: {len(spreads)}\n"
        f"  Avg spread: {avg:.4f}%\n"
        f"  Max spread: {mx:.4f}%\n"
        f"  Hours > 0.5% spread: {high_hours}"
    )


@mcp.tool()
async def get_record_roi(period: str = "day") -> str:
    """Best single trade by ROI in a given period.
    [Free]

    Args:
        period: "day" for last 24h or "week" for last 7 days
    """
    query = f"record_roi_{period}"
    data = await client.get(f"/social/run/{query}")
    result = data.get("data", {})

    if not result:
        return f"No ROI data for period: {period}"

    return (
        f"Record ROI ({period}):\n"
        f"  {result.get('symbol', '?')} — "
        f"Long {result.get('long_exchange', '?')} / Short {result.get('short_exchange', '?')}\n"
        f"  APR: {result.get('apr', 0):.1f}%\n"
        f"  ROI on $1000: ${result.get('roi_1k', 0):.2f}"
    )


@mcp.tool()
async def get_still_paying(min_hours: int = 24) -> str:
    """Pairs above 50% APR for N hours+ that are still active right now.
    [Free]

    Args:
        min_hours: Minimum consecutive hours above 50% APR (default 24, min 6)
    """
    min_hours = max(6, min_hours)
    data = await client.get(f"/social/run/still_paying?min_hours={min_hours}")
    results = data.get("data", [])

    if not results:
        return f"No pairs currently on a {min_hours}h+ streak above 50% APR."

    lines = [f"Active streaks (50%+ APR for {min_hours}h+):\n"]
    for r in results[:10]:
        lines.append(
            f"  {r.get('symbol', '?')} — {r.get('long_exchange', '?')}/{r.get('short_exchange', '?')} — "
            f"{r.get('hours', 0)}h streak, {r.get('apr', 0):.1f}% APR"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_top_holders(days: int = 7) -> str:
    """Top pairs holding 50%+ APR longest.
    [Free]

    Args:
        days: Lookback period — 7 or 14 days
    """
    query = "top_holders" if days <= 7 else "top_holders_14d"
    data = await client.get(f"/social/run/{query}")
    results = data.get("data", [])

    if not results:
        return f"No pairs held 50%+ APR in the last {days} days."

    lines = [f"Top holders (50%+ APR, last {days} days):\n"]
    for r in results[:5]:
        lines.append(
            f"  {r.get('symbol', '?')} — {r.get('long_exchange', '?')}/{r.get('short_exchange', '?')} — "
            f"{r.get('hours', 0)}h above threshold"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_momentum_movers() -> str:
    """Biggest funding spread jumps in the last 6 hours vs prior 6 hours.
    [Free]
    """
    data = await client.get("/social/run/momentum_movers")
    results = data.get("data", [])

    if not results:
        return "No significant momentum changes in the last 6 hours."

    lines = ["Momentum movers (last 6h):\n"]
    for r in results[:10]:
        cur = r.get("current_apr", 0)
        prev = r.get("prev_apr", 0)
        jump = r.get("jump", 0)
        arrow = "↑" if jump > 0 else "→"
        lines.append(
            f"  {r.get('symbol', '?')} — {r.get('long_exchange', '?')}/{r.get('short_exchange', '?')} — "
            f"{prev:.0f}% → {cur:.0f}% APR ({arrow}{jump:+.0f}%)"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_weekly_recap(days: int = 7) -> str:
    """Weekly recap: best ROI pairs, best DEX combos, most stable pair.
    [Free]

    Args:
        days: Period — 7 or 14 days
    """
    query = "weekly_recap" if days <= 7 else "weekly_recap_14d"
    data = await client.get(f"/social/run/{query}")
    result = data.get("data", {})

    if not result:
        return f"No recap data for the last {days} days."

    lines = [f"Weekly recap (last {days} days):\n"]

    if result.get("best_roi"):
        roi = result["best_roi"]
        lines.append(f"  Best ROI: {roi.get('symbol', '?')} — {roi.get('apr', 0):.1f}% APR")

    if result.get("best_dex_combo"):
        combo = result["best_dex_combo"]
        lines.append(f"  Best DEX combo: {combo.get('long', '?')}/{combo.get('short', '?')}")

    if result.get("most_stable"):
        stable = result["most_stable"]
        lines.append(f"  Most stable: {stable.get('symbol', '?')} — {stable.get('std', 0):.1f}% std dev")

    return "\n".join(lines)


@mcp.tool()
async def get_unbroken_streaks(mode: str = "top5") -> str:
    """Consecutive hours above APR threshold — multiple viewing modes.
    [Free]

    Args:
        mode: "spotlight" (random long streak), "top5" (longest 5), "fresh" (started <24h ago), "elite" (100%+ APR)
    """
    query_map = {
        "spotlight": "unbroken_streak",
        "top5": "unbroken_streak_top5",
        "fresh": "unbroken_streak_fresh",
        "elite": "unbroken_streak_elite",
    }
    query = query_map.get(mode, "unbroken_streak_top5")
    data = await client.get(f"/social/run/{query}")
    results = data.get("data", [])

    if isinstance(results, dict):
        results = [results]

    if not results:
        return f"No unbroken streaks found (mode: {mode})."

    lines = [f"Unbroken streaks ({mode}):\n"]
    for r in results[:10]:
        lines.append(
            f"  {r.get('symbol', '?')} — {r.get('long_exchange', '?')}/{r.get('short_exchange', '?')} — "
            f"{r.get('hours', 0)}h streak at {r.get('apr', 0):.1f}% APR"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_live_alpha() -> str:
    """Top 5 live funding rate arbitrage opportunities, deduplicated by symbol.
    [Free]
    """
    data = await client.get("/social/run/live_alpha")
    results = data.get("data", [])

    if not results:
        return "No live alpha opportunities right now."

    lines = ["Live alpha (top 5):\n"]
    for r in results[:5]:
        lines.append(
            f"  {r.get('symbol', '?')} — Long {r.get('long_exchange', '?')} / "
            f"Short {r.get('short_exchange', '?')} — {r.get('apr', 0):.1f}% APR"
        )

    return "\n".join(lines)


@mcp.tool()
async def find_best_trade(
    position_size: float = 1000,
    min_apr: float = 30,
    limit: int = 5,
) -> str:
    """Find the best delta-neutral trade you can open RIGHT NOW.
    Combines live funding rates + 30d backtest + spread risk + real-time order book depth.
    Returns fully-analyzed, tradeable opportunities ranked by composite risk/reward score.
    [Free]

    Args:
        position_size: How much USD you want to deploy (default 1000)
        min_apr: Minimum net APR filter (default 30)
        limit: Max results (default 5)
    """
    data = await client.get("/smart-opportunities", params={
        "position_size": position_size,
        "min_apr": min_apr,
        "limit": limit,
    })

    opps = data.get("opportunities", [])
    if not opps:
        return f"No tradeable opportunities found at ${position_size:,.0f} with ≥{min_apr}% APR."

    lines = [f"Best trades for ${position_size:,.0f} ({len(opps)} found):\n"]

    for i, o in enumerate(opps, 1):
        depth = o.get("depth", {})
        entry_cost = o.get("entry_cost_pct", 0)
        stability = o.get("stability_pct", 0)
        risk = o.get("risk_level", "unknown")
        bt_apr = o.get("backtested_apr", 0)
        days = o.get("data_days", 0)

        lines.append(f"  #{i} {o['symbol']} — Long {o['long_exchange']} / Short {o['short_exchange']}")
        lines.append(f"     Live APR: {o['net_apr']:.1f}% | 30d backtested: {bt_apr:.1f}% | Stability: {stability:.0f}%")
        lines.append(f"     Entry cost: {entry_cost:.4f}% slippage | Breakeven: {o['breakeven_days']:.1f} days")
        lines.append(f"     Risk: {risk} | Price spread: {o.get('spread_risk_pct', 0):.3f}% | Data: {days:.0f} days")
        lines.append(f"     Score: {o['score']:.1f}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_smart_opportunities(
    position_size: float = 1000,
    min_apr: float = 50,
    limit: int = 10,
) -> str:
    """Get opportunities ranked by composite score (APR × stability × liquidity).
    Unlike get_opportunities, this checks real order book depth and filters out
    pairs you can't actually trade at your position size.
    [Free]

    Args:
        position_size: Position size in USD (default 1000)
        min_apr: Minimum net APR (default 50)
        limit: Max results (default 10)
    """
    data = await client.get("/smart-opportunities", params={
        "position_size": position_size,
        "min_apr": min_apr,
        "limit": limit,
    })

    opps = data.get("opportunities", [])
    if not opps:
        return f"No tradeable opportunities at ${position_size:,.0f} with ≥{min_apr}% APR."

    lines = [f"Smart opportunities for ${position_size:,.0f} ({len(opps)} results):\n"]
    for o in opps:
        risk_emoji = {"low": "safe", "medium": "moderate", "high": "risky", "unknown": "no data"}.get(o.get("risk_level", "unknown"), "?")
        lines.append(
            f"  {o['symbol']} — {o['long_exchange']}/{o['short_exchange']} — "
            f"{o['net_apr']:.1f}% APR, {o.get('entry_cost_pct', 0):.3f}% entry cost, "
            f"risk: {risk_emoji}, score: {o['score']:.1f}"
        )

    return "\n".join(lines)


@mcp.tool()
async def check_liquidity(
    exchange: str,
    symbol: str,
    position_size: float = 1000,
) -> str:
    """Check real-time order book liquidity for a symbol on a specific exchange.
    Returns bid-ask spread, depth analysis at multiple position sizes, and slippage estimates.
    [Free]

    Args:
        exchange: Exchange name (e.g. "Hyperliquid")
        symbol: Trading pair (e.g. "ETH/USDC")
        position_size: Position size in USD for slippage estimate (default 1000)
    """
    exchange = await _normalize_exchange(exchange)
    data = await client.get(f"/liquidity/{exchange}", params={
        "symbol": symbol,
        "position_size": position_size,
    })

    if not data.get("available"):
        return f"No order book data for {symbol} on {exchange}: {data.get('message', 'unavailable')}"

    lines = [f"Liquidity: {symbol} on {data['exchange']}\n"]
    lines.append(f"  Spread: {data['spread_pct']:.4f}% ({data['bid_levels']} bid / {data['ask_levels']} ask levels)")
    lines.append(f"  Best bid: {data['best_bid']}  Best ask: {data['best_ask']}")

    if data.get("volume_24h"):
        lines.append(f"  24h volume: ${data['volume_24h']:,.0f}")
    if data.get("open_interest"):
        lines.append(f"  Open interest: ${data['open_interest']:,.0f}")

    depth = data.get("depth", {})
    if depth:
        lines.append("\n  Depth analysis:")
        for size_label, sides in depth.items():
            buy = sides.get("buy", {})
            sell = sides.get("sell", {})
            buy_slip = f"{buy['slippage_pct']:.4f}%" if buy.get("slippage_pct") is not None else "insufficient depth"
            sell_slip = f"{sell['slippage_pct']:.4f}%" if sell.get("slippage_pct") is not None else "insufficient depth"
            buy_fill = buy.get("filled_pct", 0)
            sell_fill = sell.get("filled_pct", 0)
            lines.append(f"    {size_label}: Buy slippage {buy_slip} ({buy_fill}% filled) | Sell slippage {sell_slip} ({sell_fill}% filled)")

    return "\n".join(lines)


@mcp.tool()
async def analyze_pair(
    symbol: str,
    long_exchange: str,
    short_exchange: str,
    position_size: float = 1000,
) -> str:
    """Full end-to-end analysis of a specific delta-neutral pair.
    Combines: current funding rates, 7d backtest, pair intelligence (30d risk/stability),
    live order book depth on both legs, and price spread risk — all in one call.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: Exchange to go long on
        short_exchange: Exchange to go short on
        position_size: Your intended position size in USD (default 1000)
    """
    long_exchange = await _normalize_exchange(long_exchange)
    short_exchange = await _normalize_exchange(short_exchange)
    import asyncio

    # Fetch everything in parallel
    opps_task = client.get("/opportunities", params={"symbol": symbol})
    backtest_task = client.post("/backtest", json={
        "symbol": symbol,
        "long_exchange": long_exchange,
        "short_exchange": short_exchange,
        "position_size": position_size,
        "days": 7,
        "execution_fee_bps": 10,
    })
    intel_task = client.get("/analytics/pair-intelligence")
    long_liq_task = client.get(f"/liquidity/{long_exchange}", params={
        "symbol": symbol, "position_size": position_size,
    })
    short_liq_task = client.get(f"/liquidity/{short_exchange}", params={
        "symbol": symbol, "position_size": position_size,
    })
    spread_task = client.get("/prices/chart-data", params={
        "symbol": symbol,
        "long_exchange": long_exchange,
        "short_exchange": short_exchange,
        "days": 7,
    })

    results = await asyncio.gather(
        opps_task, backtest_task, intel_task,
        long_liq_task, short_liq_task, spread_task,
        return_exceptions=True,
    )
    opps, backtest, intel_data, long_liq, short_liq, price_spread = results

    lines = [f"═══ Analysis: {symbol} — Long {long_exchange} / Short {short_exchange} ═══\n"]

    # 1. Current funding rates
    lines.append("── Current Funding ──")
    if not isinstance(opps, Exception):
        found = None
        for o in (opps if isinstance(opps, list) else []):
            if (o.get("long_exchange") == long_exchange and
                o.get("short_exchange") == short_exchange and
                o.get("symbol") == symbol):
                found = o
                break
        if found:
            lines.append(f"  Long APR: {found['long_apr']:+.1f}% | Short APR: {found['short_apr']:+.1f}%")
            lines.append(f"  Net APR: {found['net_apr']:.1f}% | Breakeven: {found.get('breakeven_days', '?')} days")
        else:
            lines.append(f"  Pair not found in current opportunities")
    else:
        lines.append(f"  Failed to fetch rates")

    # 2. Backtest
    lines.append("\n── 7-Day Backtest ──")
    if not isinstance(backtest, Exception):
        lines.append(f"  PnL: ${backtest.get('total_pnl', 0):,.2f} ({backtest.get('pnl_percentage', 0):+.2f}%)")
        lines.append(f"  Funding: ${backtest.get('total_funding_received', 0):,.2f} | Fees: ${backtest.get('total_fees_paid', 0):,.2f}")
        lines.append(f"  Sharpe: {backtest.get('sharpe_ratio', 0):.2f}")
        if backtest.get("has_price_data") and backtest.get("spread_pnl") is not None:
            lines.append(f"  Price spread PnL: ${backtest['spread_pnl']:,.2f}")
        hist_slip = backtest.get("historical_slippage_bps")
        if hist_slip is not None:
            lines.append(f"  Historical slippage: {hist_slip:.1f} bps")
    else:
        lines.append(f"  Backtest failed")

    # 3. Pair intelligence
    lines.append("\n── 30-Day Intelligence ──")
    if not isinstance(intel_data, Exception):
        pair_key = f"{symbol}|{long_exchange}|{short_exchange}"
        intel = intel_data.get("pairs", {}).get(pair_key, {})
        if intel:
            depth_label = {1.0: "$10k+", 0.8: "$5-10k", 0.5: "$1-5k", 0.2: "<$1k"}.get(
                intel.get("depth_score"), "unknown")
            lines.append(f"  Smart score: {intel.get('smart_score', 0):.1f}")
            lines.append(f"  Backtested APR: {intel.get('backtested_net_apr', 0):.1f}%")
            lines.append(f"  Stability: {intel.get('stability_pct', 0):.0f}% of hours profitable")
            lines.append(f"  Risk level: {intel.get('risk_level', 'unknown')}")
            lines.append(f"  Depth tier: {depth_label}")
            lines.append(f"  Data: {intel.get('data_days', 0):.1f} days of history")
        else:
            lines.append(f"  No intelligence data for this pair")
    else:
        lines.append(f"  Intelligence fetch failed")

    # 4. Live liquidity — both legs
    for side, liq, ex_name in [("Long", long_liq, long_exchange), ("Short", short_liq, short_exchange)]:
        lines.append(f"\n── {side} Leg: {ex_name} ──")
        if isinstance(liq, Exception):
            lines.append(f"  Liquidity check failed")
            continue
        if not liq.get("available"):
            lines.append(f"  {liq.get('message', 'No order book data available')}")
            continue
        lines.append(f"  Spread: {liq['spread_pct']:.4f}% | Levels: {liq['bid_levels']} bid / {liq['ask_levels']} ask")
        if liq.get("volume_24h"):
            lines.append(f"  24h volume: ${liq['volume_24h']:,.0f}")
        depth = liq.get("depth", {})
        size_key = f"${int(position_size)}"
        if size_key not in depth:
            size_key = "$1000"  # fallback
        if size_key in depth:
            buy = depth[size_key].get("buy", {})
            sell = depth[size_key].get("sell", {})
            buy_slip = f"{buy['slippage_pct']:.4f}%" if buy.get("slippage_pct") is not None else f"{buy.get('filled_pct', 0):.0f}% filled"
            sell_slip = f"{sell['slippage_pct']:.4f}%" if sell.get("slippage_pct") is not None else f"{sell.get('filled_pct', 0):.0f}% filled"
            lines.append(f"  At {size_key}: buy slippage {buy_slip} | sell slippage {sell_slip}")

    # 5. Price spread risk
    lines.append("\n── Price Spread Risk (7d) ──")
    if not isinstance(price_spread, Exception):
        points = price_spread if isinstance(price_spread, list) else price_spread.get("data", [])
        if points:
            spreads = [p.get("spread_pct", 0) for p in points if p.get("spread_pct") is not None]
            if spreads:
                lines.append(f"  Avg divergence: {sum(spreads)/len(spreads):.4f}%")
                lines.append(f"  Max divergence: {max(spreads):.4f}%")
                lines.append(f"  Data points: {len(spreads)}")
            else:
                lines.append(f"  No spread data in response")
        else:
            lines.append(f"  No price history between these exchanges")
    else:
        lines.append(f"  Price spread fetch failed")

    return "\n".join(lines)


@mcp.tool()
async def compare_exchanges(
    symbol: str,
    exchanges: str = "",
) -> str:
    """Compare the same symbol across multiple exchanges — funding rates, spread, depth, volume.
    Helps decide which exchange to use for each leg of a delta-neutral trade.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        exchanges: Comma-separated exchange names to compare (e.g. "Hyperliquid,dYdX,Aster"). If empty, shows all exchanges that list this symbol.
    """
    import asyncio

    # Get opportunities to find which exchanges list this symbol
    opps = await client.get("/opportunities", params={"symbol": symbol})
    if isinstance(opps, dict) and "detail" in opps:
        return f"Error: {opps['detail']}"

    # Collect unique exchanges and their raw funding rate for this symbol
    # Raw rate: positive = longs pay shorts. short_apr = raw rate, long_apr = -raw rate.
    exchange_set = set()
    exchange_rates = {}
    for o in (opps if isinstance(opps, list) else []):
        if o.get("symbol") != symbol:
            continue
        if o["long_exchange"] not in exchange_rates:
            exchange_rates[o["long_exchange"]] = -o["long_apr"]  # negate: long_apr is PnL when long
        if o["short_exchange"] not in exchange_rates:
            exchange_rates[o["short_exchange"]] = o["short_apr"]  # short_apr = raw rate
        exchange_set.add(o["long_exchange"])
        exchange_set.add(o["short_exchange"])

    if exchanges:
        mapping = await _get_exchange_map()
        filter_set = {mapping.get(e.strip().lower(), e.strip()) for e in exchanges.split(",")}
        exchange_set = exchange_set & filter_set
        if not exchange_set:
            return f"None of [{exchanges}] list {symbol}. Available: {', '.join(sorted(exchange_rates.keys()))}"

    if not exchange_set:
        return f"No exchanges found for {symbol}"

    # Fetch liquidity for each exchange in parallel
    liq_results = await asyncio.gather(
        *[client.get(f"/liquidity/{ex}", params={"symbol": symbol, "position_size": 5000})
          for ex in sorted(exchange_set)],
        return_exceptions=True,
    )

    lines = [f"═══ {symbol} — Exchange Comparison ═══\n"]

    for ex, liq in zip(sorted(exchange_set), liq_results):
        apr = exchange_rates.get(ex)
        apr_str = f"{apr:+.1f}%" if apr is not None else "?"

        lines.append(f"  {ex}")
        lines.append(f"    Funding APR: {apr_str}")

        if isinstance(liq, Exception) or not liq.get("available"):
            lines.append(f"    Liquidity: no data")
        else:
            lines.append(f"    Spread: {liq['spread_pct']:.4f}%")
            if liq.get("volume_24h"):
                lines.append(f"    24h volume: ${liq['volume_24h']:,.0f}")
            depth = liq.get("depth", {})
            d5k = depth.get("$5000", {}).get("buy", {})
            if d5k.get("slippage_pct") is not None:
                lines.append(f"    $5k buy slippage: {d5k['slippage_pct']:.4f}%")
            elif d5k.get("filled_pct") is not None:
                lines.append(f"    $5k fill: {d5k['filled_pct']:.0f}%")
        lines.append("")

    return "\n".join(lines)


# ─── Trading Tools (Free) ────────────────────────────────────

@mcp.tool()
async def store_credentials(exchange: str, credentials: str) -> str:
    """Store exchange credentials for AI trading. Encrypted with AES-256-GCM on the server.
    [Free]

    SECURITY WARNING: Credentials pass through this conversation and may be logged
    by your AI provider. Only provide agent/signer keys (trade-only, no withdrawal).
    For maximum security, use the web form at profunding.pro/keys instead.

    Args:
        exchange: Exchange name. Supported: Hyperliquid, Lighter, Aster, Pacifica.
            HIP-3 DEXes (TradeXYZ, DreamCash, etc.) use Hyperliquid credentials.
        credentials: JSON string with exchange-specific fields:
            Hyperliquid: {"wallet_address": "0x...", "agent_address": "0x...", "agent_private_key": "0x...", "builder": "defiapp"}
              (add "builder": "defiapp" if you authenticated via defi.app — required for correct builder fee signing)
            Lighter: {"api_private_key": "...", "api_public_key": "...", "account_index": 0}
            Aster: {"wallet_address": "0x...", "signer_address": "0x...", "signer_private_key": "0x..."}
            Pacifica: {"solana_address": "...", "agent_address": "...", "agent_private_key": "..."}
    """
    import json as _json
    try:
        creds_dict = _json.loads(credentials)
    except _json.JSONDecodeError:
        return "Error: credentials must be a valid JSON string."

    try:
        data = await client.post("/credentials", json={
            "exchange": exchange,
            "credentials": creds_dict,
        })
        return f"Credentials stored for {data.get('exchange', exchange)}."
    except Exception as e:
        return f"Failed to store credentials: {e}"


@mcp.tool()
async def list_credentials() -> str:
    """List exchanges where you have stored credentials for AI trading.
    [Free]
    """
    try:
        data = await client.get("/credentials")
        if not data:
            return "No credentials stored. Use store_credentials to add exchange keys."
        lines = ["Stored credentials:"]
        for c in data:
            status = "enabled" if c["enabled"] else "DISABLED"
            last = c.get("last_used_at", "never")
            lines.append(f"  {c['exchange']} — {status}, last used: {last}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list credentials: {e}"


@mcp.tool()
async def revoke_credentials(exchange: str) -> str:
    """Remove stored credentials for an exchange. This stops AI trading on that exchange.
    [Free]

    Args:
        exchange: Exchange name to revoke credentials for.
    """
    try:
        data = await client.delete(f"/credentials/{exchange}")
        return f"Credentials revoked for {data.get('exchange', exchange)}."
    except Exception as e:
        return f"Failed to revoke credentials: {e}"


@mcp.tool()
async def revoke_all_credentials() -> str:
    """KILL SWITCH: Remove ALL stored credentials and stop all AI trading immediately.
    [Free]
    """
    try:
        data = await client.delete("/credentials")
        return f"All credentials revoked. {data.get('count', 0)} exchanges removed."
    except Exception as e:
        return f"Failed to revoke all credentials: {e}"


@mcp.tool()
async def open_trade(
    exchange: str,
    symbol: str,
    side: str,
    size_usd: float,
    leverage: int = 5,
) -> str:
    """Open a single trade on an exchange using stored credentials.
    [Free]

    Args:
        exchange: Exchange name (e.g. "Hyperliquid", "Lighter")
        symbol: Trading pair (e.g. "ETH/USDC", "BTC/USDC")
        side: "long" or "short"
        size_usd: Position size in USD per leg
        leverage: Leverage multiplier (default 5)
    """
    try:
        data = await client.post("/mcp/trade/open", json={
            "exchange": exchange,
            "symbol": symbol,
            "side": side,
            "size_usd": size_usd,
            "leverage": leverage,
        })
        return (
            f"Order placed on {exchange}:\n"
            f"  {side.upper()} {symbol}, ${size_usd} at {leverage}x\n"
            f"  Order ID: {data.get('order_id')}\n"
            f"  Status: {data.get('status')}\n"
            f"  Fill price: {data.get('filled_price')}"
        )
    except Exception as e:
        return f"Trade failed: {e}"


@mcp.tool()
async def close_trade(exchange: str, symbol: str, side: str) -> str:
    """Close an open position on an exchange using stored credentials.
    [Free]

    Args:
        exchange: Exchange name
        symbol: Trading pair (e.g. "ETH/USDC")
        side: "long" or "short" — the side you want to close
    """
    try:
        data = await client.post("/mcp/trade/close", json={
            "exchange": exchange,
            "symbol": symbol,
            "side": side,
        })
        return (
            f"Position closed on {exchange}:\n"
            f"  {side.upper()} {symbol}\n"
            f"  Status: {data.get('status')}\n"
            f"  Fill price: {data.get('filled_price')}"
        )
    except Exception as e:
        return f"Close failed: {e}"


@mcp.tool()
async def open_delta_neutral(
    symbol: str,
    long_exchange: str,
    short_exchange: str,
    size_usd: float = 1000,
    leverage: int = 5,
) -> str:
    """Open a delta-neutral funding arbitrage position — long on one exchange, short on another.
    Both legs are market orders. On partial failure, the successful leg is NOT auto-closed.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: Exchange to go long on (the one paying you negative funding)
        short_exchange: Exchange to go short on (the one paying you positive funding)
        size_usd: Size per leg in USD (default 1000)
        leverage: Leverage multiplier (default 5)
    """
    try:
        data = await client.post("/mcp/trade/open-dn", json={
            "symbol": symbol,
            "long_exchange": long_exchange,
            "short_exchange": short_exchange,
            "size_usd": size_usd,
            "leverage": leverage,
        })

        status = data.get("status", "unknown")
        lines = [f"Delta-neutral position: {status.upper()}"]
        lines.append(f"  Position ID: {data.get('position_id')}")
        lines.append(f"  {symbol} — Long {long_exchange} / Short {short_exchange}")
        lines.append(f"  Size: ${size_usd}/leg at {leverage}x")

        if data.get("long_leg"):
            ll = data["long_leg"]
            lines.append(f"  Long: {ll.get('status')} @ {ll.get('filled_price')}")
        if data.get("short_leg"):
            sl = data["short_leg"]
            lines.append(f"  Short: {sl.get('status')} @ {sl.get('filled_price')}")
        if data.get("error"):
            lines.append(f"  ⚠ {data['error']}")

        return "\n".join(lines)
    except Exception as e:
        return f"DN open failed: {e}"


@mcp.tool()
async def close_delta_neutral(
    symbol: str = "",
    long_exchange: str = "",
    short_exchange: str = "",
    position_id: str = "",
) -> str:
    """Close a delta-neutral position (both legs). Provide either position_id or symbol+exchanges.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: Exchange where you're long
        short_exchange: Exchange where you're short
        position_id: Server position ID (alternative to symbol+exchanges)
    """
    body = {}
    if position_id:
        body["position_id"] = position_id
    else:
        body["symbol"] = symbol
        body["long_exchange"] = long_exchange
        body["short_exchange"] = short_exchange

    try:
        data = await client.post("/mcp/trade/close-dn", json=body)

        lines = [f"DN position closed: {data.get('status', 'unknown').upper()}"]
        if data.get("pnl_usd") is not None:
            lines.append(f"  PnL: ${data['pnl_usd']:.2f}")
        if data.get("long_leg"):
            ll = data["long_leg"]
            lines.append(f"  Long close: {ll.get('status')} @ {ll.get('filled_price')}")
        if data.get("short_leg"):
            sl = data["short_leg"]
            lines.append(f"  Short close: {sl.get('status')} @ {sl.get('filled_price')}")

        return "\n".join(lines)
    except Exception as e:
        return f"DN close failed: {e}"


@mcp.tool()
async def get_positions(exchange: str = "") -> str:
    """List open positions. If exchange specified, queries that DEX's live API.
    Otherwise shows server-tracked delta-neutral positions.
    [Free]

    Args:
        exchange: Optional exchange name. If empty, shows DN positions from server.
    """
    try:
        params = {}
        if exchange:
            params["exchange"] = exchange
        data = await client.get("/mcp/trade/positions", params=params)

        if not data:
            return "No open positions."

        lines = [f"Open positions ({len(data)}):"]
        for p in data:
            if "long_exchange" in p:
                # DN position
                lines.append(
                    f"  {p['symbol']} — Long {p['long_exchange']} / Short {p['short_exchange']}\n"
                    f"    Size: ${p['size_usd']}, Status: {p['status']}, "
                    f"Opened: {p.get('opened_at', 'N/A')}"
                )
            else:
                # Single exchange position
                lines.append(
                    f"  {p.get('exchange', exchange)}: {p['side'].upper()} {p['symbol']} "
                    f"size={p['size']:.4f} entry={p['entry_price']:.4f} "
                    f"pnl={p.get('unrealized_pnl', 0):.2f}"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to get positions: {e}"


@mcp.tool()
async def get_balance(exchange: str) -> str:
    """Check your balance on an exchange using stored credentials.
    [Free]

    Args:
        exchange: Exchange name (e.g. "Hyperliquid", "Lighter")
    """
    try:
        data = await client.get("/mcp/trade/balance", params={"exchange": exchange})
        lines = [f"Balance on {data.get('exchange', exchange)}:"]
        spot = data.get("spot_balances", [])
        if spot:
            for s in spot:
                lines.append(f"  {s['coin']}: ${s['available']:.2f}")
        else:
            lines.append(f"  {data.get('currency', 'USDC')}: ${data.get('available', 0):.2f}")
        if data.get('locked', 0) > 0:
            lines.append(f"  Locked (margin): ${data['locked']:.2f}")
        lines.append(f"  Total: ${data.get('total', 0):.2f}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to get balance: {e}"


@mcp.tool()
async def convert_stablecoin(
    from_coin: str,
    to_coin: str,
    amount: float,
) -> str:
    """Convert stablecoins on Hyperliquid (USDC <-> USDE/USDT0/USDH).
    Uses stored credentials — agent-signed, no wallet popup needed.
    Useful for moving collateral between HIP-3 DEXes that use different stablecoins.
    [Free]

    Args:
        from_coin: Source stablecoin (e.g. "USDC", "USDE", "USDT0", "USDH")
        to_coin: Target stablecoin (e.g. "USDE", "USDC")
        amount: Amount to convert (in from_coin units)
    """
    try:
        data = await client.post("/mcp/trade/convert", json={
            "from_coin": from_coin,
            "to_coin": to_coin,
            "amount": amount,
        })
        return (
            f"Converted {from_coin} → {to_coin}:\n"
            f"  Filled: {data.get('filled_size', '0')} {to_coin}\n"
            f"  Avg price: {data.get('avg_price', '0')}"
        )
    except Exception as e:
        return f"Convert failed: {e}"


# ─── Monitoring Tools (Free) ─────────────────────────────────


@mcp.tool()
async def watch_position(
    symbol: str,
    long_exchange: str,
    short_exchange: str,
    funding_flip_alert: bool = True,
    min_apr_threshold: float = 0,
    pnl_threshold_pct: float = 0,
    max_duration_hours: int = 0,
    auto_close: bool = False,
    close_on_trigger: bool = False,
) -> str:
    """Set up backend monitoring for a delta-neutral position.
    The system checks conditions every 60 seconds and can auto-close or alert via Telegram.
    [Free]

    Args:
        symbol: Trading pair (e.g. "ETH/USDC")
        long_exchange: Exchange where the long position is held
        short_exchange: Exchange where the short position is held
        funding_flip_alert: Alert when net funding rate flips negative (default: true)
        min_apr_threshold: Alert when APR drops below this value (0 = disabled)
        pnl_threshold_pct: Alert when PnL drops below this % of margin (e.g. -5.0 for -5%, 0 = disabled)
        max_duration_hours: Auto-alert after this many hours (0 = disabled)
        auto_close: Enable automated position closing (requires stored credentials)
        close_on_trigger: If true + auto_close, positions are closed automatically on trigger. If false, only alerts.
    """
    try:
        data = await client.post("/mcp/trade/watch", json={
            "symbol": symbol,
            "long_exchange": long_exchange,
            "short_exchange": short_exchange,
            "funding_flip_alert": funding_flip_alert,
            "min_apr_threshold": min_apr_threshold,
            "pnl_threshold_pct": pnl_threshold_pct,
            "max_duration_hours": max_duration_hours,
            "auto_close": auto_close,
            "close_on_trigger": close_on_trigger,
        })

        lines = [
            f"Position watch created (ID: {data.get('watch_id', 'N/A')})",
            f"  Pair: {data.get('symbol')} — Long {data.get('long_exchange')} / Short {data.get('short_exchange')}",
            f"  Auto-close: {'enabled' if data.get('auto_close') else 'disabled'}",
            f"  Close on trigger: {'yes' if data.get('close_on_trigger') else 'no (alert only)'}",
            f"  Telegram linked: {'yes' if data.get('telegram_linked') else 'no (no TG alerts)'}",
        ]
        conditions = []
        if funding_flip_alert:
            conditions.append("funding flip")
        if min_apr_threshold > 0:
            conditions.append(f"APR < {min_apr_threshold}%")
        if pnl_threshold_pct < 0:
            conditions.append(f"PnL < {pnl_threshold_pct}%")
        if max_duration_hours > 0:
            conditions.append(f"duration > {max_duration_hours}h")
        lines.append(f"  Conditions: {', '.join(conditions) if conditions else 'none'}")

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to create position watch: {e}"


@mcp.tool()
async def get_alerts(active_only: bool = True) -> str:
    """Get monitoring alerts for your watched positions.
    Shows recent alerts with their type, details, and action taken.
    [Free]

    Args:
        active_only: If true, only show alerts for active watches (default: true)
    """
    try:
        data = await client.get("/mcp/trade/alerts", params={"active_only": str(active_only).lower()})

        if not data:
            return "No alerts found."

        lines = [f"Monitoring alerts ({len(data)}):"]
        for a in data:
            detail = a.get("detail", {})
            detail_str = ", ".join(f"{k}={v}" for k, v in detail.items() if k != "close_result")
            lines.append(
                f"  [{a.get('created_at', 'N/A')}] {a.get('alert_type', 'unknown')}: "
                f"{detail_str} — {a.get('action_taken', 'pending')}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to get alerts: {e}"


# ─── Server entry point ──────────────────────────────────────

def main():
    """Run the MCP server (stdio transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
