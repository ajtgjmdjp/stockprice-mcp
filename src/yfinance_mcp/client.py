"""Yahoo Finance client wrapping yfinance."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from loguru import logger


@dataclass
class StockPrice:
    source: str
    code: str
    ticker: str
    date: str
    close: float
    open: float
    high: float
    low: float
    volume: int
    week52_high: float
    week52_low: float
    avg_volume_30d: int | None = None
    avg_volume_90d: int | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    market_cap: int | None = None
    sector: str | None = None
    trailing_eps: float | None = None
    dividend_yield: float | None = None


@dataclass
class PriceHistory:
    source: str
    ticker: str
    start: str
    end: str
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FxRates:
    source: str
    rates: dict[str, float]


class YfinanceClient:
    """Thin async wrapper around yfinance for MCP use."""

    # FX pairs supported
    FX_PAIRS: dict[str, str] = {
        "USDJPY": "USDJPY=X",
        "EURJPY": "EURJPY=X",
        "GBPJPY": "GBPJPY=X",
        "CNYJPY": "CNYJPY=X",
    }

    async def get_stock_price(
        self,
        code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> StockPrice | None:
        """Fetch latest stock price for a TSE-listed stock (code.T)."""
        import yfinance as yf

        ticker_symbol = f"{code}.T"

        def _fetch() -> tuple[Any, dict[str, Any]]:
            ticker = yf.Ticker(ticker_symbol)
            if start_date or end_date:
                hist = ticker.history(
                    start=str(start_date) if start_date else None,
                    end=str(end_date) if end_date else None,
                )
            else:
                hist = ticker.history(period="1y")
            try:
                raw_info = ticker.info
                info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else {}
            except Exception:
                info = {}
            return hist, info

        try:
            hist, info = await asyncio.to_thread(_fetch)
            if hist.empty:
                logger.warning(f"yfinance returned empty data for {ticker_symbol}")
                return None

            latest = hist.iloc[-1]
            avg_vol_30d = float(hist["Volume"].tail(30).mean()) if len(hist) >= 30 else None
            avg_vol_90d = float(hist["Volume"].tail(90).mean()) if len(hist) >= 90 else None

            result = StockPrice(
                source="yfinance",
                code=code,
                ticker=ticker_symbol,
                date=str(hist.index[-1].date()),
                close=float(latest["Close"]),
                open=float(latest["Open"]),
                high=float(latest["High"]),
                low=float(latest["Low"]),
                volume=int(latest["Volume"]),
                week52_high=float(hist["High"].max()),
                week52_low=float(hist["Low"].min()),
                avg_volume_30d=int(avg_vol_30d) if avg_vol_30d else None,
                avg_volume_90d=int(avg_vol_90d) if avg_vol_90d else None,
            )

            for attr, key in [
                ("trailing_pe", "trailingPE"),
                ("forward_pe", "forwardPE"),
                ("price_to_book", "priceToBook"),
                ("market_cap", "marketCap"),
                ("sector", "sector"),
                ("trailing_eps", "trailingEps"),
            ]:
                val = info.get(key)
                if val is not None:
                    setattr(result, attr, val)

            dy_raw = info.get("dividendYield")
            if isinstance(dy_raw, (int, float)) and dy_raw > 0:
                result.dividend_yield = dy_raw / 100.0 if dy_raw >= 1.0 else dy_raw

            return result
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {ticker_symbol}: {e}")
            return None

    async def get_stock_history(
        self,
        code: str,
        *,
        start_date: str,
        end_date: str | None = None,
        interval: str = "1d",
    ) -> PriceHistory | None:
        """Fetch OHLCV history for a TSE-listed stock."""
        import yfinance as yf

        ticker_symbol = f"{code}.T"

        def _fetch() -> Any:
            ticker = yf.Ticker(ticker_symbol)
            return ticker.history(start=start_date, end=end_date, interval=interval)

        try:
            hist = await asyncio.to_thread(_fetch)
            if hist.empty:
                return None

            rows = [
                {
                    "date": str(idx.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
                for idx, row in hist.iterrows()
            ]

            return PriceHistory(
                source="yfinance",
                ticker=ticker_symbol,
                start=str(hist.index[0].date()),
                end=str(hist.index[-1].date()),
                rows=rows,
            )
        except Exception as e:
            logger.warning(f"yfinance history failed for {ticker_symbol}: {e}")
            return None

    async def get_fx_rates(
        self,
        pairs: list[str] | None = None,
    ) -> FxRates | None:
        """Fetch JPY FX rates. Defaults to USDJPY, EURJPY, GBPJPY, CNYJPY."""
        import yfinance as yf

        target = {k: v for k, v in self.FX_PAIRS.items() if pairs is None or k in pairs}

        def _fetch() -> dict[str, float]:
            result: dict[str, float] = {}
            for name, sym in target.items():
                try:
                    t = yf.Ticker(sym)
                    hist = t.history(period="5d")
                    if not hist.empty:
                        result[name] = float(hist["Close"].iloc[-1])
                except Exception:
                    pass
            return result

        try:
            rates = await asyncio.to_thread(_fetch)
            if not rates:
                return None
            return FxRates(source="yfinance_fx", rates=rates)
        except Exception as e:
            logger.warning(f"FX fetch failed: {e}")
            return None

    async def search_ticker(self, query: str) -> list[dict[str, Any]]:
        """Search Yahoo Finance for a ticker by company name or keyword."""
        import yfinance as yf

        def _fetch() -> list[dict[str, Any]]:
            search = yf.Search(query, max_results=10)
            results = []
            for item in search.quotes:
                results.append(
                    {
                        "symbol": item.get("symbol", ""),
                        "short_name": item.get("shortname", ""),
                        "long_name": item.get("longname", ""),
                        "exchange": item.get("exchange", ""),
                        "type": item.get("quoteType", ""),
                    }
                )
            return results

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.warning(f"yfinance search failed: {e}")
            return []
