"""Tests for error and edge-case paths in YfinanceClient.

Covers: network timeouts, missing DataFrame columns, custom date ranges,
non-dict ticker.info, avg_volume boundary conditions, malformed history rows,
incomplete search results, and FX timeout handling.
"""

from __future__ import annotations

from datetime import date as dt_date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from yfinance_mcp.client import YfinanceClient, _build_stock_price


def _make_hist(rows: list[dict]) -> pd.DataFrame:
    dates = pd.to_datetime([r["date"] for r in rows])
    df = pd.DataFrame(rows, index=dates)
    df.index.name = "Date"
    return df


def _rows(n: int, *, start_day: int = 1) -> list[dict]:
    """Generate *n* OHLCV sample rows starting from 2025-01-{start_day}."""
    return [
        {
            "date": f"2025-{(start_day + i - 1) // 28 + 1:02d}-{(start_day + i - 1) % 28 + 1:02d}",
            "Open": 1000.0 + i,
            "High": 1100.0 + i,
            "Low": 900.0 + i,
            "Close": 1050.0 + i,
            "Volume": 500000 + i * 100,
        }
        for i in range(n)
    ]


SINGLE_ROW = _rows(1)


# ---------------------------------------------------------------------------
# Network timeout / ConnectionError
# ---------------------------------------------------------------------------


class TestNetworkTimeout:
    """Timeout and connection errors should return None, not raise."""

    @pytest.mark.asyncio
    async def test_get_stock_price_timeout(self):
        with patch("yfinance.Ticker", side_effect=TimeoutError("connection timed out")):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stock_price_connection_error(self):
        with patch("yfinance.Ticker", side_effect=ConnectionError("refused")):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stock_history_timeout(self):
        with patch("yfinance.Ticker", side_effect=TimeoutError("timed out")):
            client = YfinanceClient()
            result = await client.get_stock_history("7203", start_date="2025-01-01")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_fx_rates_timeout(self):
        """Timeout on an individual FX pair should be silently skipped."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = ConnectionError("network unreachable")

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_fx_rates(["USDJPY"])
        # ConnectionError is subclass of OSError, caught per-pair → empty rates → None
        assert result is None

    @pytest.mark.asyncio
    async def test_search_ticker_timeout(self):
        with patch("yfinance.Search", side_effect=TimeoutError("search timed out")):
            client = YfinanceClient()
            results = await client.search_ticker("Toyota")
        assert results == []


# ---------------------------------------------------------------------------
# Missing columns in DataFrame (KeyError path)
# ---------------------------------------------------------------------------


class TestMissingColumns:
    """DataFrame with missing expected columns should be handled gracefully."""

    @pytest.mark.asyncio
    async def test_stock_price_missing_close_column(self):
        """DataFrame without 'Close' → KeyError caught → None."""
        rows = [{
            "date": "2025-01-01", "Open": 1000.0,
            "High": 1100.0, "Low": 900.0, "Volume": 500000,
        }]
        dates = pd.to_datetime(["2025-01-01"])
        df = pd.DataFrame(rows, index=dates)

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")
        # KeyError from missing 'Close' column is caught by the except clause
        assert result is None

    @pytest.mark.asyncio
    async def test_history_missing_volume_column(self):
        """History DataFrame without 'Volume' → KeyError caught → None."""
        rows = [{
            "date": "2025-01-01", "Open": 1000.0,
            "High": 1100.0, "Low": 900.0, "Close": 1050.0,
        }]
        dates = pd.to_datetime(["2025-01-01"])
        df = pd.DataFrame(rows, index=dates)

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("7203", start_date="2025-01-01")
        # KeyError from missing 'Volume' caught → None
        assert result is None


# ---------------------------------------------------------------------------
# Custom date range in get_stock_price
# ---------------------------------------------------------------------------


class TestCustomDateRange:
    """get_stock_price with explicit start_date/end_date exercises a different _fetch branch."""

    @pytest.mark.asyncio
    async def test_with_start_date_only(self):
        hist = _make_hist(SINGLE_ROW)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203", start_date=dt_date(2025, 1, 1))

        assert result is not None
        assert result.code == "7203"
        # Verify that history() was called with start= and end=None
        mock_ticker.history.assert_called_once_with(start="2025-01-01", end=None)

    @pytest.mark.asyncio
    async def test_with_both_dates(self):
        hist = _make_hist(SINGLE_ROW)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price(
                "7203", start_date=dt_date(2025, 1, 1), end_date=dt_date(2025, 1, 31)
            )

        assert result is not None
        mock_ticker.history.assert_called_once_with(start="2025-01-01", end="2025-01-31")


# ---------------------------------------------------------------------------
# ticker.info returning non-dict
# ---------------------------------------------------------------------------


class TestInfoNonDict:
    """ticker.info can return non-dict values (e.g. string, list, None)."""

    @pytest.mark.asyncio
    async def test_info_returns_none(self):
        hist = _make_hist(SINGLE_ROW)

        def make_ticker(sym):
            t = MagicMock()
            t.history.return_value = hist
            type(t).info = property(lambda self: None)
            return t

        with patch("yfinance.Ticker", side_effect=make_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        # Fundamentals should all be None since info was not a dict
        assert result.trailing_pe is None
        assert result.sector is None

    @pytest.mark.asyncio
    async def test_info_returns_list(self):
        hist = _make_hist(SINGLE_ROW)

        def make_ticker(sym):
            t = MagicMock()
            t.history.return_value = hist
            type(t).info = property(lambda self: ["unexpected", "data"])
            return t

        with patch("yfinance.Ticker", side_effect=make_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.trailing_pe is None


# ---------------------------------------------------------------------------
# avg_volume boundary conditions
# ---------------------------------------------------------------------------


class TestAvgVolumeBoundary:
    """Test boundary conditions for 30-day and 90-day average volume."""

    @pytest.mark.asyncio
    async def test_exactly_30_rows(self):
        """With exactly 30 rows, avg_volume_30d should be computed."""
        hist = _make_hist(_rows(30))
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.avg_volume_30d is not None
        assert result.avg_volume_90d is None  # Only 30 rows, need 90

    @pytest.mark.asyncio
    async def test_29_rows_no_30d_avg(self):
        """With 29 rows, avg_volume_30d should be None."""
        hist = _make_hist(_rows(29))
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.avg_volume_30d is None
        assert result.avg_volume_90d is None

    @pytest.mark.asyncio
    async def test_exactly_90_rows(self):
        """With exactly 90 rows, both avg_volume_30d and avg_volume_90d should be computed."""
        hist = _make_hist(_rows(90))
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.avg_volume_30d is not None
        assert result.avg_volume_90d is not None


# ---------------------------------------------------------------------------
# Search with incomplete quote dicts
# ---------------------------------------------------------------------------


class TestSearchIncompleteQuotes:
    """Search results with missing keys should use defaults from .get()."""

    @pytest.mark.asyncio
    async def test_quotes_missing_all_optional_keys(self):
        """Quotes with no expected keys — all fields default to empty string."""
        mock_search = MagicMock()
        mock_search.quotes = [{}]

        with patch("yfinance.Search", return_value=mock_search):
            client = YfinanceClient()
            results = await client.search_ticker("test")

        assert len(results) == 1
        assert results[0]["symbol"] == ""
        assert results[0]["short_name"] == ""
        assert results[0]["long_name"] == ""
        assert results[0]["exchange"] == ""
        assert results[0]["type"] == ""

    @pytest.mark.asyncio
    async def test_quotes_with_partial_keys(self):
        """Only some keys present — missing ones default to empty string."""
        mock_search = MagicMock()
        mock_search.quotes = [{"symbol": "7203.T", "exchange": "TSE"}]

        with patch("yfinance.Search", return_value=mock_search):
            client = YfinanceClient()
            results = await client.search_ticker("Toyota")

        assert len(results) == 1
        assert results[0]["symbol"] == "7203.T"
        assert results[0]["short_name"] == ""
        assert results[0]["long_name"] == ""
        assert results[0]["exchange"] == "TSE"


# ---------------------------------------------------------------------------
# _build_stock_price unit tests
# ---------------------------------------------------------------------------


class TestBuildStockPrice:
    """Direct unit tests for the _build_stock_price helper."""

    def test_single_row_no_avg_volumes(self):
        hist = _make_hist(SINGLE_ROW)
        result = _build_stock_price("1234", "1234.T", hist, {})

        assert result.code == "1234"
        assert result.ticker == "1234.T"
        assert result.close == pytest.approx(1050.0)
        assert result.avg_volume_30d is None
        assert result.avg_volume_90d is None
        assert result.trailing_pe is None

    def test_with_full_fundamentals(self):
        hist = _make_hist(SINGLE_ROW)
        info = {
            "trailingPE": 10.0,
            "forwardPE": 9.5,
            "priceToBook": 1.1,
            "marketCap": 1_000_000_000,
            "sector": "Technology",
            "trailingEps": 150.0,
            "dividendYield": 0.03,
        }
        result = _build_stock_price("5678", "5678.T", hist, info)

        assert result.trailing_pe == 10.0
        assert result.forward_pe == 9.5
        assert result.price_to_book == 1.1
        assert result.market_cap == 1_000_000_000
        assert result.sector == "Technology"
        assert result.trailing_eps == 150.0
        assert result.dividend_yield == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# ValueErrors in client methods
# ---------------------------------------------------------------------------


class TestValueError:
    """ValueError raised from yfinance internals should be caught."""

    @pytest.mark.asyncio
    async def test_stock_price_valueerror(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = ValueError("invalid period")

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")
        assert result is None

    @pytest.mark.asyncio
    async def test_history_valueerror(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = ValueError("bad interval")

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("7203", start_date="2025-01-01")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_valueerror(self):
        with patch("yfinance.Search", side_effect=ValueError("bad query")):
            client = YfinanceClient()
            results = await client.search_ticker("test")
        assert results == []
