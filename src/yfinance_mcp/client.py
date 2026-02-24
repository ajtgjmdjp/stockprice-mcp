"""Yahoo Finance client wrapping yfinance."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from loguru import logger
from yfinance.exceptions import YFException

if TYPE_CHECKING:
    from datetime import date

    import pandas as pd


@dataclass
class StockPrice:
    """Latest stock price snapshot with fundamentals for a TSE-listed stock.

    Attributes:
        source: Data provider identifier (e.g. ``"yfinance"``).
        code: 4-digit TSE stock code (e.g. ``"7203"``).
        ticker: Yahoo Finance ticker symbol (e.g. ``"7203.T"``).
        date: Date of the latest price in ``YYYY-MM-DD`` format.
        close: Latest closing price.
        open: Latest opening price.
        high: Latest daily high.
        low: Latest daily low.
        volume: Latest daily trading volume.
        week52_high: 52-week high price.
        week52_low: 52-week low price.
        avg_volume_30d: 30-day average volume, or ``None`` if fewer than 30 days.
        avg_volume_90d: 90-day average volume, or ``None`` if fewer than 90 days.
        trailing_pe: Trailing P/E ratio, if available.
        forward_pe: Forward P/E ratio, if available.
        price_to_book: Price-to-book ratio, if available.
        market_cap: Market capitalisation in JPY, if available.
        sector: Company sector classification, if available.
        trailing_eps: Trailing earnings per share, if available.
        dividend_yield: Dividend yield as a decimal (e.g. 0.025 = 2.5%), if available.
    """

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
    """OHLCV price history for a TSE-listed stock.

    Attributes:
        source: Data provider identifier (e.g. ``"yfinance"``).
        ticker: Yahoo Finance ticker symbol (e.g. ``"7203.T"``).
        start: Start date of the returned data in ``YYYY-MM-DD`` format.
        end: End date of the returned data in ``YYYY-MM-DD`` format.
        rows: List of OHLCV dicts, each with keys ``date``, ``open``,
            ``high``, ``low``, ``close``, ``volume``.
    """

    source: str
    ticker: str
    start: str
    end: str
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FxRates:
    """JPY foreign exchange rates snapshot.

    Attributes:
        source: Data provider identifier (e.g. ``"yfinance_fx"``).
        rates: Mapping of pair name (e.g. ``"USDJPY"``) to rate value.
    """

    source: str
    rates: dict[str, float]


def _extract_fundamentals(info: dict[str, Any]) -> dict[str, Any]:
    """Extract fundamental data from a yfinance ``ticker.info`` dict.

    Pulls trailing/forward P/E, P/B, market cap, sector, trailing EPS,
    and dividend yield.  Dividend yield values >= 1.0 are assumed to be
    percentages and are converted to decimals.

    Args:
        info: The ``ticker.info`` dict returned by yfinance.

    Returns:
        Dict of fundamental fields suitable for unpacking into
        :class:`StockPrice`.  Keys absent from *info* are omitted.
    """
    result: dict[str, Any] = {}
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
            result[attr] = val

    dy_raw = info.get("dividendYield")
    if isinstance(dy_raw, (int, float)) and dy_raw > 0:
        result["dividend_yield"] = dy_raw / 100.0 if dy_raw >= 1.0 else dy_raw

    return result


def _build_stock_price(
    code: str, ticker_symbol: str, hist: pd.DataFrame, info: dict[str, Any]
) -> StockPrice:
    """Build a :class:`StockPrice` from yfinance history and info.

    Args:
        code: 4-digit TSE stock code (e.g. ``"7203"``).
        ticker_symbol: Yahoo Finance ticker (e.g. ``"7203.T"``).
        hist: Non-empty OHLCV DataFrame returned by ``ticker.history()``.
        info: The ``ticker.info`` dict (may be empty on fetch failure).

    Returns:
        Populated :class:`StockPrice` instance.
    """
    latest = hist.iloc[-1]
    avg_vol_30d = float(hist["Volume"].tail(30).mean()) if len(hist) >= 30 else None
    avg_vol_90d = float(hist["Volume"].tail(90).mean()) if len(hist) >= 90 else None

    fundamentals = _extract_fundamentals(info)
    return StockPrice(
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
        **fundamentals,
    )


class YfinanceClient:
    """Thin async wrapper around yfinance for MCP use."""

    # FX pairs supported
    FX_PAIRS: ClassVar[dict[str, str]] = {
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
        """Fetch the latest stock price and fundamentals for a TSE-listed stock.

        Appends ``.T`` to *code* and queries yfinance for 1-year history
        (or the given date range) plus fundamental data.

        Args:
            code: 4-digit TSE stock code (e.g. ``"7203"`` for Toyota).
            start_date: Optional start date to override the default 1-year
                lookback.
            end_date: Optional end date (defaults to today).

        Returns:
            A :class:`StockPrice` with the latest OHLCV data and
            fundamentals, or ``None`` if the ticker is invalid or
            yfinance returns no data.
        """
        import yfinance as yf

        ticker_symbol = f"{code}.T"

        def _fetch() -> tuple[pd.DataFrame, dict[str, Any]]:
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
            except (YFException, ValueError, KeyError, AttributeError, OSError):
                # ticker.info can fail: YFException (rate limit, missing data),
                # KeyError/AttributeError (unexpected response), OSError (network)
                info = {}
            return hist, info

        try:
            hist, info = await asyncio.to_thread(_fetch)
            if hist.empty:
                logger.warning(f"yfinance returned empty data for {ticker_symbol}")
                return None

            return _build_stock_price(code, ticker_symbol, hist, info)
        except (YFException, ValueError, KeyError, OSError) as e:
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
        """Fetch OHLCV price history for a TSE-listed stock.

        Args:
            code: 4-digit TSE stock code (e.g. ``"7203"``).
            start_date: Start date in ``YYYY-MM-DD`` format.
            end_date: End date in ``YYYY-MM-DD`` format.  Defaults to today.
            interval: Data interval — ``"1d"`` (daily), ``"1wk"`` (weekly),
                or ``"1mo"`` (monthly).

        Returns:
            A :class:`PriceHistory` containing the OHLCV rows, or ``None``
            if the ticker is invalid or no data is available for the range.
        """
        import yfinance as yf

        ticker_symbol = f"{code}.T"

        def _fetch() -> pd.DataFrame:
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
        except (YFException, ValueError, KeyError, OSError) as e:
            logger.warning(f"yfinance history failed for {ticker_symbol}: {e}")
            return None

    async def get_fx_rates(
        self,
        pairs: list[str] | None = None,
    ) -> FxRates | None:
        """Fetch JPY foreign exchange rates.

        Queries yfinance for the latest closing rate of each requested
        currency pair.  Individual pair failures are silently skipped.

        Args:
            pairs: Currency pair names to fetch (e.g. ``["USDJPY", "EURJPY"]``).
                Supported: ``USDJPY``, ``EURJPY``, ``GBPJPY``, ``CNYJPY``.
                Defaults to all four if ``None``.

        Returns:
            An :class:`FxRates` with the available rates, or ``None`` if
            every pair fails.
        """
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
                except (YFException, ValueError, KeyError, OSError):
                    # Skip pair on yfinance errors or network failures
                    pass
            return result

        try:
            rates = await asyncio.to_thread(_fetch)
            if not rates:
                return None
            return FxRates(source="yfinance_fx", rates=rates)
        except (YFException, ValueError, KeyError, OSError) as e:
            logger.warning(f"FX fetch failed: {e}")
            return None

    async def search_ticker(self, query: str) -> list[dict[str, Any]]:
        """Search Yahoo Finance for a ticker by company name or keyword.

        Args:
            query: Company name or keyword to search (e.g. ``"Toyota"``,
                ``"ソニー"``, ``"Nikkei ETF"``).

        Returns:
            List of dicts with keys ``symbol``, ``short_name``,
            ``long_name``, ``exchange``, and ``type``.  Returns an
            empty list if the search fails or finds no matches.
        """
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
        except (YFException, ValueError, KeyError, OSError) as e:
            logger.warning(f"yfinance search failed: {e}")
            return []
