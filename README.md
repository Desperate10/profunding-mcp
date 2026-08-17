# ProFunding MCP Server

Trade funding rate arbitrage across 20+ perpetual DEXes from your AI assistant — find opportunities, open delta-neutral positions, supervise them to optimal exit. Backed by [ProFunding](https://profunding.pro).

## Quick start

```bash
pip install profunding-mcp
claude mcp add profunding profunding-mcp -e PROFUNDING_API_KEY=pfk_your_key_here
```

Free API key at [profunding.pro](https://profunding.pro). Market-data tools work without one.

## Setup

### About the API key

Most tools (trading, account, find-exit, deep analytics) need an API key. Keys are **free** at [profunding.pro](https://profunding.pro) — sign up takes seconds, no credit card. Market-data and backtest tools work without one.

### Claude Code without a key (market-data only)

```bash
claude mcp add profunding profunding-mcp
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
| `PROFUNDING_API_KEY` | For most tools | Free key from [profunding.pro](https://profunding.pro). Trading, account, find-exit, and deep analytics need one; market-data tools work without one. |

### Auto-approve trade tools (Claude Code)

Claude Code asks for confirmation before each call to a trade tool. To approve them once per project, add the trade allowlist to `.claude/settings.local.json` in that project's root (or `~/.claude/settings.json` for global):

```json
{
  "permissions": {
    "allow": [
      "mcp__profunding__open_trade",
      "mcp__profunding__close_trade",
      "mcp__profunding__cancel_order",
      "mcp__profunding__open_delta_neutral",
      "mcp__profunding__close_delta_neutral",
      "mcp__profunding__convert_stablecoin",
      "mcp__profunding__twap_open_dn",
      "mcp__profunding__twap_close_dn",
      "mcp__profunding__twap_cancel"
    ]
  }
}
```

Note: Claude's built-in safety policies may still decline crypto trading actions even with the allowlist in place — the allowlist clears permission prompts, not Claude's own safety check on financial actions. If trades get declined, phrase the request as an explicit authorization (e.g. *"I authorize a $5 long ETH on Lighter via `open_trade`. Execute now."*) or use Claude Code's plan mode.

## Tools (44)

The `Auth` column shows whether a tool needs an API key:
- **open** — public, no key needed
- **key** — needs a free API key (wallet-bound for find-exit / trading)

### Market Data & Discovery (12, all open)

| Tool | Auth | Description |
|------|------|-------------|
| `get_opportunities` | open | Live funding rate arbitrage opportunities across all DEXes |
| `get_exchanges` | open | List connected DEXes with status and funding interval |
| `get_historical_rates` | open | Historical funding rates for a symbol on one exchange |
| `get_rate_chart_data` | open | Funding rate spread over time between two exchanges |
| `get_price_spread_data` | open | Mark price divergence between two exchanges (price risk analysis) |
| `run_backtest` | open | Backtest a delta-neutral trade with real historical data |
| `analyze_pair` | open | Full end-to-end analysis: funding + backtest + risk + depth on both legs + price spread |
| `compare_exchanges` | open | Side-by-side comparison of same symbol across exchanges: rates, spread, depth, volume |
| `find_best_trade` | open | Best trade you can open right now at your position size — ranked by net APR after fees, liquidity, and risk |
| `get_smart_opportunities` | open | Opportunities ranked by how tradable they actually are — APR, depth, and stability combined |
| `get_pair_intelligence` | open | Risk scores, backtested APR, smart ranking, depth tiers for all pairs |
| `check_liquidity` | open | Real-time order book depth + slippage estimates at $1k/$5k/$10k |

### Deep Analytics (7, key required)

| Tool | Auth | Description |
|------|------|-------------|
| `get_live_alpha` | key | Top 5 deduplicated opportunities |
| `get_still_paying` | key | Pairs above 50% APR for 24h+ still active now |
| `get_top_holders` | key | Pairs holding high APR the longest |
| `get_momentum_movers` | key | Biggest funding spread jumps in last 6 hours |
| `get_unbroken_streaks` | key | Consecutive hours above APR threshold |
| `get_record_roi` | key | Best single trade by ROI in a period |
| `get_weekly_recap` | key | Best ROI pair, best DEX combo, most stable pair |

### Trading (5, key required)

| Tool | Auth | Description |
|------|------|-------------|
| `open_trade` | key | Open a single-leg position on one DEX — **market, or a resting `limit` order** (`order_type="limit"` + `limit_price`, every tradable DEX) |
| `close_trade` | key | Close a single-leg position on one DEX — market, or a resting reduce-only **limit** close (`limit_price`, every tradable DEX) |
| `open_delta_neutral` | key | Open a delta-neutral pair: long one DEX, short another (market) |
| `close_delta_neutral` | key | Close both legs of a delta-neutral pair (market) |
| `convert_stablecoin` | key | Convert between USDC / USDT / other stablecoins where supported |

### Limit Orders (3, key required)

Resting limit orders on **every tradable DEX** (aster, hyperliquid + HIP-3 sub-DEXes, lighter, pacifica, hibachi, extended, nado, grvt, 01xyz, variational, ethereal, hotstuff, risex, perpl, phoenix, ondo). A limit order from `open_trade` returns immediately with `status="open"` and an order id; manage it with these. `post_only` is honored on all of them **except lighter, 01xyz and variational**, where it is accepted but not enforceable — the order rests as a plain GTT that may take if marketable, and the response carries a warning saying so. On **ondo** post-only is enforced by *rejection* (`post_only_has_match` means your price would have crossed — reprice, don't retry blind), and a reduce-only limit is emulated by capping size to the live position, because reduce-only cannot ride a GTC limit there. **Per-DEX cancel id:** most DEXes' `open_trade` order id is cancellable directly; **Lighter resting orders must be located via `get_open_orders` first** — its `open_trade` response is a tx hash, not a cancellable id, so list-then-cancel.

| Tool | Auth | Description |
|------|------|-------------|
| `get_open_orders` | key | List your resting limit orders on a DEX (Lighter requires a symbol; its returned id is what `cancel_order` needs) |
| `cancel_order` | key | Cancel a resting limit order by its cancellable order id |
| `get_order_fills` | key | Check whether a limit order filled and finalize builder-fee accounting (pass the `trade_log_id` from `open_trade`) |

### TWAP (5, key required)

Backend-orchestrated TWAP that slices a delta-neutral **open** or **close** over time with per-slice slippage protection. Runs server-side (no client needed) — start it, then poll. Supported DEXes: hyperliquid, extended, pacifica, aster, lighter, grvt, hibachi, ethereal, 01xyz, nado, variational (+ HIP-3).

| Tool | Auth | Description |
|------|------|-------------|
| `twap_open_dn` | key | Gradually OPEN a delta-neutral pair (margin-sized) — slices into both legs over a time window |
| `twap_close_dn` | key | Gradually CLOSE a delta-neutral pair — slices both legs out over a time window |
| `twap_job_status` | key | Status + progress of a TWAP job (open or close) |
| `twap_cancel` | key | Stop a running TWAP job at the next slice boundary (filled slices are not rolled back) |
| `twap_jobs` | key | List your recent TWAP jobs (open + close) |

### Account (3, key required)

| Tool | Auth | Description |
|------|------|-------------|
| `get_positions` | key | List your open positions across all DEXes with credentials stored |
| `get_balance` | key | Read account balances from each connected DEX |
| `get_alerts` | key | Position alerts and monitoring events triggered for your wallet |

### Credentials (4, key required)

| Tool | Auth | Description |
|------|------|-------------|
| `store_credentials` | key | Save API keys / signer keys for a DEX (encrypted server-side) |
| `list_credentials` | key | List which DEXes have credentials stored, with last-verified status |
| `revoke_credentials` | key | Remove stored credentials for one DEX |
| `revoke_all_credentials` | key | Remove all stored credentials |

### Find Exit (4, key required)

Optimal-exit search for an open delta-neutral position. Backend monitors the spread peak and exits when conditions confirm the trade has stopped paying.

| Tool | Auth | Description |
|------|------|-------------|
| `find_exit_preview` | key | Preview what an optimal exit would look like for a position (peak/target/current) |
| `find_exit_start` | key | Start a find-exit job on a position with target APR / max wait constraints |
| `find_exit_status` | key | Read current state of a find-exit job (anchor, peak, drawdown, ticks) |
| `find_exit_cancel` | key | Cancel an active find-exit job and leave the position open |

### Monitoring (1, key required)

| Tool | Auth | Description |
|------|------|-------------|
| `watch_position` | key | Set up alert thresholds for a position (drawdown, funding sign flip, etc) — fires via Telegram |

## Example Queries

Once connected, ask your AI assistant:

**Discovery & analysis** (work without a key)
- "What's the best trade I can open right now with $5k?"
- "Analyze ETH/USDC on Extended vs Aster — is it worth entering?"
- "Compare ETH funding rates across Hyperliquid, Aster, and Extended"
- "Check liquidity for SOL on Pacifica — can I fill $10k?"
- "Run a 30-day backtest on BTC long Lighter short Hyperliquid"

**Trading** (need a key)
- "Open a $200 delta-neutral on ETH: long Hyperliquid, short Aster"
- "What positions do I have open?"
- "Close my BTC delta-neutral pair"
- "Find the optimal exit for my SOL/USDC position with a 50% target APR"
- "Place a resting limit buy of $50 ETH on Aster at 3000, then show my open orders"
- "TWAP into a $1000 delta-neutral on SOL (long Lighter, short Aster) over 20 minutes, then check the job status"

**Credentials** (need a key)
- "Store my Hyperliquid API key — I'll paste the wallet and signer below"
- "Which DEXes do I have credentials for?"

## Get a Key

Visit [profunding.pro](https://profunding.pro) to claim your free API key. Bound to your wallet so trading and find-exit can sign and route orders on your behalf.
