"""Tests for YfinanceClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from yfinance_mcp.client import FxRates, PriceHistory, StockPrice, YfinanceClient


def _make_hist(rows: list[dict]) -> pd.DataFrame:
    import pandas as pd
    from datetime import date

    dates = pd.to_datetime([r["date"] for r in rows])
    df = pd.DataFrame(rows, index=dates)
    df.index.name = "Date"
    return df


SAMPLE_ROWS = [
    {"date": f"2025-01-{i:02d}", "Open": 2000.0 + i, "High": 2100.0 + i, "Low": 1900.0 + i, "Close": 2050.0 + i, "Volume": 1000000}
    for i in range(1, 32)
]


class TestGetStockPrice:
    @pytest.mark.asyncio
    async def test_returns_stock_price(self):
        hist = _make_hist(SAMPLE_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {"trailingPE": 12.5, "marketCap": 50000000000, "sector": "Consumer Cyclical"}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert isinstance(result, StockPrice)
        assert result.code == "7203"
        assert result.ticker == "7203.T"
        assert result.close == pytest.approx(2050.0 + 31)
        assert result.week52_high == pytest.approx(max(r["High"] for r in SAMPLE_ROWS))
        assert result.week52_low == pytest.approx(min(r["Low"] for r in SAMPLE_ROWS))
        assert result.trailing_pe == 12.5
        assert result.sector == "Consumer Cyclical"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("9999")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        with patch("yfinance.Ticker", side_effect=Exception("network error")):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is None

    @pytest.mark.asyncio
    async def test_dividend_yield_normalization(self):
        hist = _make_hist(SAMPLE_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        # Japanese stocks sometimes return percentage (e.g. 2.56 instead of 0.0256)
        mock_ticker.info = {"dividendYield": 2.56}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.dividend_yield == pytest.approx(0.0256)

    @pytest.mark.asyncio
    async def test_dividend_yield_decimal(self):
        hist = _make_hist(SAMPLE_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {"dividendYield": 0.0256}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.dividend_yield == pytest.approx(0.0256)


class TestGetStockHistory:
    @pytest.mark.asyncio
    async def test_returns_history(self):
        hist = _make_hist(SAMPLE_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("7203", start_date="2025-01-01")

        assert isinstance(result, PriceHistory)
        assert result.ticker == "7203.T"
        assert len(result.rows) == len(SAMPLE_ROWS)
        assert "close" in result.rows[0]
        assert "volume" in result.rows[0]

    @pytest.mark.asyncio
    async def test_returns_none_on_empty(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("9999", start_date="2025-01-01")

        assert result is None


class TestGetFxRates:
    @pytest.mark.asyncio
    async def test_returns_fx_rates(self):
        def _make_fx_hist(close_val: float) -> pd.DataFrame:
            dates = pd.to_datetime(["2025-01-01", "2025-01-02"])
            return pd.DataFrame({"Close": [close_val, close_val]}, index=dates)

        mock_tickers = {
            "USDJPY=X": MagicMock(history=MagicMock(return_value=_make_fx_hist(150.0))),
            "EURJPY=X": MagicMock(history=MagicMock(return_value=_make_fx_hist(160.0))),
            "GBPJPY=X": MagicMock(history=MagicMock(return_value=_make_fx_hist(190.0))),
            "CNYJPY=X": MagicMock(history=MagicMock(return_value=_make_fx_hist(20.0))),
        }

        with patch("yfinance.Ticker", side_effect=lambda sym: mock_tickers[sym]):
            client = YfinanceClient()
            result = await client.get_fx_rates()

        assert isinstance(result, FxRates)
        assert result.rates["USDJPY"] == pytest.approx(150.0)
        assert result.rates["EURJPY"] == pytest.approx(160.0)

    @pytest.mark.asyncio
    async def test_subset_pairs(self):
        def _make_fx_hist(v: float) -> pd.DataFrame:
            return pd.DataFrame({"Close": [v]}, index=pd.to_datetime(["2025-01-01"]))

        mock_tickers = {
            "USDJPY=X": MagicMock(history=MagicMock(return_value=_make_fx_hist(150.0))),
        }

        with patch("yfinance.Ticker", side_effect=lambda sym: mock_tickers[sym]):
            client = YfinanceClient()
            result = await client.get_fx_rates(["USDJPY"])

        assert result is not None
        assert "USDJPY" in result.rates
        assert "EURJPY" not in result.rates

    @pytest.mark.asyncio
    async def test_returns_none_on_all_empty(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_fx_rates()

        assert result is None


class TestSearchTicker:
    @pytest.mark.asyncio
    async def test_returns_results(self):
        mock_search = MagicMock()
        mock_search.quotes = [
            {"symbol": "7203.T", "shortname": "TOYOTA MOTOR", "longname": "Toyota Motor Corporation", "exchange": "TSE", "quoteType": "EQUITY"},
        ]

        with patch("yfinance.Search", return_value=mock_search):
            client = YfinanceClient()
            results = await client.search_ticker("Toyota")

        assert len(results) == 1
        assert results[0]["symbol"] == "7203.T"

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        with patch("yfinance.Search", side_effect=Exception("search failed")):
            client = YfinanceClient()
            results = await client.search_ticker("xxx")

        assert results == []
