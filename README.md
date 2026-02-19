# stockprice-mcp

Stock price & FX rate MCP server for Claude Desktop, powered by [yfinance](https://github.com/ranaroussi/yfinance). No API key required.

> **Note**: An unrelated package named `yfinance-mcp` exists on PyPI — it is not affiliated with this project.
> This project is published as **`stockprice-mcp`**.

## Setup (Claude Desktop)

```bash
uvx stockprice-mcp serve
```

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stockprice": {
      "command": "uvx",
      "args": ["stockprice-mcp", "serve"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `get_stock_price` | Latest price + fundamentals for TSE-listed stocks (code.T) |
| `get_stock_history` | OHLCV history for a date range |
| `get_fx_rates` | JPY FX rates (USDJPY, EURJPY, GBPJPY, CNYJPY) |
| `search_ticker` | Search ticker by company name or keyword |

## Usage in Claude Desktop

```text
stockprice でトヨタ（7203）の最新株価を教えて
```

```text
stockprice で USDJPY の直近1週間の推移を確認して
```

```text
stockprice でソニーのティッカーを検索して
```

## CLI

```bash
pip install stockprice-mcp

yfinance-mcp price 7203                        # 最新株価
yfinance-mcp history 7203 --start 2025-01-01   # 価格履歴
yfinance-mcp fx                                # FXレート
yfinance-mcp search Toyota                     # ティッカー検索
yfinance-mcp test                              # 疎通確認
yfinance-mcp serve                             # MCPサーバー起動
```

## Python

```python
import asyncio
from yfinance_mcp import YfinanceClient

async def main():
    client = YfinanceClient()
    price = await client.get_stock_price("7203")
    print(price.close, price.trailing_pe)

asyncio.run(main())
```

## Disclaimer

This package uses [yfinance](https://github.com/ranaroussi/yfinance) (Apache 2.0) to access Yahoo Finance data.
yfinance is not affiliated with or endorsed by Yahoo.
Users are responsible for complying with [Yahoo Finance's Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/).
Data is intended for personal, educational, and research use.

## License

Apache-2.0
