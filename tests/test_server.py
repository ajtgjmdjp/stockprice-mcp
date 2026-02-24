"""Tests for MCP server tool functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from yfinance_mcp.client import FxRates, PriceHistory, StockPrice
from yfinance_mcp.server import get_fx_rates, get_stock_history, get_stock_price, search_ticker

SAMPLE_STOCK = StockPrice(
    source="yfinance",
    code="7203",
    ticker="7203.T",
    date="2025-01-31",
    close=2081.0,
    open=2031.0,
    high=2131.0,
    low=1931.0,
    volume=1000000,
    week52_high=2131.0,
    week52_low=1901.0,
    trailing_pe=12.5,
    market_cap=50000000000,
    sector="Consumer Cyclical",
)

SAMPLE_HISTORY = PriceHistory(
    source="yfinance",
    ticker="7203.T",
    start="2025-01-01",
    end="2025-01-03",
    rows=[
        {
            "date": "2025-01-01",
            "open": 2000.0,
            "high": 2100.0,
            "low": 1900.0,
            "close": 2050.0,
            "volume": 100000,
        },
        {
            "date": "2025-01-02",
            "open": 2050.0,
            "high": 2150.0,
            "low": 1950.0,
            "close": 2100.0,
            "volume": 110000,
        },
        {
            "date": "2025-01-03",
            "open": 2100.0,
            "high": 2200.0,
            "low": 2000.0,
            "close": 2150.0,
            "volume": 120000,
        },
    ],
)

SAMPLE_FX = FxRates(source="yfinance_fx", rates={"USDJPY": 150.0, "EURJPY": 160.0})

SAMPLE_SEARCH = [
    {
        "symbol": "7203.T",
        "short_name": "TOYOTA MOTOR",
        "long_name": "Toyota Motor Corporation",
        "exchange": "TSE",
        "type": "EQUITY",
    },
]


class TestGetStockPrice:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_price = AsyncMock(return_value=SAMPLE_STOCK)
            result = await get_stock_price("7203")

        assert result["code"] == "7203"
        assert result["ticker"] == "7203.T"
        assert result["close"] == 2081.0
        assert result["sector"] == "Consumer Cyclical"
        mock_client.get_stock_price.assert_awaited_once_with("7203")

    @pytest.mark.asyncio
    async def test_returns_error_on_none(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_price = AsyncMock(return_value=None)
            result = await get_stock_price("9999")

        assert "error" in result
        assert "9999" in result["error"]


class TestGetStockHistory:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=SAMPLE_HISTORY)
            result = await get_stock_history("7203", start_date="2025-01-01")

        assert result["ticker"] == "7203.T"
        assert result["count"] == 3
        assert result["start"] == "2025-01-01"
        assert result["end"] == "2025-01-03"
        assert len(result["data"]) == 3
        mock_client.get_stock_history.assert_awaited_once_with(
            "7203", start_date="2025-01-01", end_date=None, interval="1d"
        )

    @pytest.mark.asyncio
    async def test_with_optional_params(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=SAMPLE_HISTORY)
            result = await get_stock_history(
                "7203", start_date="2025-01-01", end_date="2025-01-31", interval="1wk"
            )

        assert result["source"] == "yfinance"
        mock_client.get_stock_history.assert_awaited_once_with(
            "7203", start_date="2025-01-01", end_date="2025-01-31", interval="1wk"
        )

    @pytest.mark.asyncio
    async def test_returns_error_on_none(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=None)
            result = await get_stock_history("9999", start_date="2025-01-01")

        assert "error" in result
        assert "9999" in result["error"]


class TestGetFxRates:
    @pytest.mark.asyncio
    async def test_success_default_pairs(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_fx_rates = AsyncMock(return_value=SAMPLE_FX)
            result = await get_fx_rates()

        assert result["source"] == "yfinance_fx"
        assert result["rates"]["USDJPY"] == 150.0
        assert result["rates"]["EURJPY"] == 160.0
        mock_client.get_fx_rates.assert_awaited_once_with(None)

    @pytest.mark.asyncio
    async def test_success_with_pairs(self):
        fx = FxRates(source="yfinance_fx", rates={"USDJPY": 150.0})
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_fx_rates = AsyncMock(return_value=fx)
            result = await get_fx_rates(pairs=["USDJPY"])

        assert "USDJPY" in result["rates"]
        mock_client.get_fx_rates.assert_awaited_once_with(["USDJPY"])

    @pytest.mark.asyncio
    async def test_returns_error_on_none(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_fx_rates = AsyncMock(return_value=None)
            result = await get_fx_rates()

        assert "error" in result


class TestSearchTicker:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.search_ticker = AsyncMock(return_value=SAMPLE_SEARCH)
            result = await search_ticker("Toyota")

        assert len(result) == 1
        assert result[0]["symbol"] == "7203.T"
        mock_client.search_ticker.assert_awaited_once_with("Toyota")

    @pytest.mark.asyncio
    async def test_returns_message_on_empty(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.search_ticker = AsyncMock(return_value=[])
            result = await search_ticker("nonexistent")

        assert len(result) == 1
        assert "message" in result[0]
        assert "nonexistent" in result[0]["message"]

    @pytest.mark.asyncio
    async def test_returns_message_on_none(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.search_ticker = AsyncMock(return_value=None)
            result = await search_ticker("xxx")

        assert len(result) == 1
        assert "message" in result[0]
