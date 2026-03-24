# ProFunding MCP Server

MCP server for [ProFunding](https://profunding.pro) — AI-powered funding rate arbitrage across 20+ perpetual DEXes.

Analyze delta-neutral opportunities, check real-time liquidity, run backtests, and get deep analytics directly from your AI assistant.

## Installation

```bash
pip install profunding-mcp
```

## Setup

### Claude Code

```bash
claude mcp add profunding profunding-mcp -e PROFUNDING_API_KEY=pfk_your_key_here
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "profunding": {
      "command": "profunding-mcp",
      "env": {
        "PROFUNDING_API_KEY": "pfk_your_key_here"
      }
    }
  }
}
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PROFUNDING_API_KEY` | Yes (for paid tools) | API key from [profunding.pro](https://profunding.pro). Free tier works without key. |

## Tools (20)

### Free Tier

| Tool | Description |
|------|-------------|
| `get_opportunities` | Live funding rate arbitrage opportunities across all DEXes |
| `get_exchanges` | List connected DEXes with status and funding interval |
| `get_historical_rates` | Historical funding rates for a symbol on one exchange |
| `run_backtest` | Backtest a delta-neutral trade with real historical data |
| `get_rate_chart_data` | Funding rate spread over time between two exchanges |

### Paid Tier — Analysis

| Tool | Description |
|------|-------------|
| `analyze_pair` | Full end-to-end analysis: funding + backtest + risk + depth on both legs + price spread — one call |
| `compare_exchanges` | Side-by-side comparison of same symbol across exchanges: rates, spread, depth, volume |
| `find_best_trade` | Best trade you can open RIGHT NOW at your position size — ranked by composite score |
| `get_smart_opportunities` | Opportunities ranked by tradability (APR x stability x depth x data confidence) |
| `check_liquidity` | Real-time order book depth + slippage estimates at $1k/$5k/$10k |
| `get_pair_intelligence` | Risk scores, backtested APR, smart ranking, depth tiers for all pairs |
| `get_price_spread_data` | Mark price divergence between two exchanges (price risk analysis) |

### Paid Tier — Analytics

| Tool | Description |
|------|-------------|
| `get_live_alpha` | Top 5 deduplicated opportunities |
| `get_still_paying` | Pairs above 50% APR for 24h+ still active now |
| `get_top_holders` | Pairs holding high APR the longest |
| `get_momentum_movers` | Biggest funding spread jumps in last 6 hours |
| `get_weekly_recap` | Best ROI pair, best DEX combo, most stable pair |
| `get_unbroken_streaks` | Consecutive hours above APR threshold |
| `get_record_roi` | Best single trade by ROI in a period |

## Example Queries

Once connected, ask your AI assistant:

- "What's the best trade I can open right now with $5k?"
- "Analyze MEGA/USDC on Extended/Aster — is it worth entering?"
- "Compare ETH funding rates across Hyperliquid, dYdX, and Aster"
- "Check liquidity for SOL on Paradex — can I fill $10k?"
- "Run a 30-day backtest on XMR long Nado short dYdX"
- "Which pairs have been paying above 50% for 3+ days straight?"
- "What moved the most in the last 6 hours?"

## Get an API Key

Visit [profunding.pro](https://profunding.pro) to get your API key.
