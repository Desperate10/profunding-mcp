# ProFunding MCP Server

MCP server for [ProFunding](https://profunding.pro) — funding rate arbitrage across 20+ perpetual DEXes, with AI-driven trading.

Analyze opportunities, check liquidity, run backtests, manage credentials, open and close delta-neutral positions, and supervise them with optimal-exit search — all directly from your AI assistant.

## Installation

```bash
pip install profunding-mcp
```

## Setup

### Claude Code

```bash
claude mcp add profunding profunding-mcp
```

If you want higher quota / per-key usage tracking, add an API key:

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

The `env` block is optional — every tool works without an API key.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PROFUNDING_API_KEY` | No | Optional API key from [profunding.pro](https://profunding.pro) for higher quota and per-key usage tracking. All tools work without it. |

## Tools (36)

All tools are available without an API key.

### Market Data & Analytics (19)

| Tool | Description |
|------|-------------|
| `get_opportunities` | Live funding rate arbitrage opportunities across all DEXes |
| `get_exchanges` | List connected DEXes with status and funding interval |
| `get_historical_rates` | Historical funding rates for a symbol on one exchange |
| `get_rate_chart_data` | Funding rate spread over time between two exchanges |
| `get_price_spread_data` | Mark price divergence between two exchanges (price risk analysis) |
| `run_backtest` | Backtest a delta-neutral trade with real historical data |
| `analyze_pair` | Full end-to-end analysis: funding + backtest + risk + depth on both legs + price spread |
| `compare_exchanges` | Side-by-side comparison of same symbol across exchanges: rates, spread, depth, volume |
| `find_best_trade` | Best trade you can open right now at your position size — ranked by composite score |
| `get_smart_opportunities` | Opportunities ranked by tradability (APR × stability × depth × data confidence) |
| `get_pair_intelligence` | Risk scores, backtested APR, smart ranking, depth tiers for all pairs |
| `check_liquidity` | Real-time order book depth + slippage estimates at $1k/$5k/$10k |
| `get_live_alpha` | Top 5 deduplicated opportunities |
| `get_still_paying` | Pairs above 50% APR for 24h+ still active now |
| `get_top_holders` | Pairs holding high APR the longest |
| `get_momentum_movers` | Biggest funding spread jumps in last 6 hours |
| `get_unbroken_streaks` | Consecutive hours above APR threshold |
| `get_record_roi` | Best single trade by ROI in a period |
| `get_weekly_recap` | Best ROI pair, best DEX combo, most stable pair |

### Trading (5)

| Tool | Description |
|------|-------------|
| `open_trade` | Open a single-leg market position on one DEX (uses your stored credentials) |
| `close_trade` | Close a single-leg position on one DEX |
| `open_delta_neutral` | Open a delta-neutral pair: long one DEX, short another |
| `close_delta_neutral` | Close both legs of a delta-neutral pair atomically |
| `convert_stablecoin` | Convert between USDC / USDT / other stablecoins where supported |

### Account (3)

| Tool | Description |
|------|-------------|
| `get_positions` | List your open positions across all DEXes with credentials stored |
| `get_balance` | Read account balances from each connected DEX |
| `get_alerts` | Position alerts and monitoring events triggered for your wallet |

### Credentials (4)

| Tool | Description |
|------|-------------|
| `store_credentials` | Save API keys / signer keys for a DEX (encrypted server-side) |
| `list_credentials` | List which DEXes have credentials stored, with last-verified status |
| `revoke_credentials` | Remove stored credentials for one DEX |
| `revoke_all_credentials` | Remove all stored credentials |

### Find Exit (4)

Optimal-exit search for an open delta-neutral position. Backend monitors the spread peak and exits when conditions confirm the trade has stopped paying.

| Tool | Description |
|------|-------------|
| `find_exit_preview` | Preview what an optimal exit would look like for a position (peak/target/current) |
| `find_exit_start` | Start a find-exit job on a position with target APR / max wait constraints |
| `find_exit_status` | Read current state of a find-exit job (anchor, peak, drawdown, ticks) |
| `find_exit_cancel` | Cancel an active find-exit job and leave the position open |

### Monitoring (1)

| Tool | Description |
|------|-------------|
| `watch_position` | Set up alert thresholds for a position (drawdown, funding sign flip, etc) — fires via Telegram |

## Example Queries

Once connected, ask your AI assistant:

**Discovery & analysis**
- "What's the best trade I can open right now with $5k?"
- "Analyze ETH/USDC on Extended vs Aster — is it worth entering?"
- "Compare ETH funding rates across Hyperliquid, Aster, and Extended"
- "Check liquidity for SOL on Pacifica — can I fill $10k?"
- "Run a 30-day backtest on BTC long Lighter short Hyperliquid"
- "Which pairs have been paying above 50% for 3+ days straight?"

**Trading**
- "Open a $200 delta-neutral on ETH: long Hyperliquid, short Aster"
- "What positions do I have open?"
- "Close my BTC delta-neutral pair"
- "Find the optimal exit for my SOL/USDC position with a 50% target APR"

**Credentials**
- "Store my Hyperliquid API key — I'll paste the wallet and signer below"
- "Which DEXes do I have credentials for?"

## Get an API Key (optional)

Visit [profunding.pro](https://profunding.pro) to claim a key for higher per-IP quota and per-account usage tracking. The MCP server works without a key.
