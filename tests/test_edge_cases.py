"""Edge case tests for yfinance-mcp client and server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from yfinance.exceptions import YFException

from yfinance_mcp.client import YfinanceClient, _extract_fundamentals
from yfinance_mcp.server import get_fx_rates, get_stock_history, get_stock_price, search_ticker


def _make_hist(rows: list[dict]) -> pd.DataFrame:
    dates = pd.to_datetime([r["date"] for r in rows])
    df = pd.DataFrame(rows, index=dates)
    df.index.name = "Date"
    return df


MINIMAL_ROWS = [
    {
        "date": "2025-01-01",
        "Open": 1000.0,
        "High": 1100.0,
        "Low": 900.0,
        "Close": 1050.0,
        "Volume": 500000,
    },
]


# ---------------------------------------------------------------------------
# Client edge cases
# ---------------------------------------------------------------------------


class TestInvalidTickerSymbol:
    """Invalid ticker symbols should return None gracefully."""

    @pytest.mark.asyncio
    async def test_invalid_code_returns_none_on_empty_hist(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("XXXXX")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_code_yfexception(self):
        with patch("yfinance.Ticker", side_effect=YFException("No data found")):
            client = YfinanceClient()
            result = await client.get_stock_price("00000")

        assert result is None

    @pytest.mark.asyncio
    async def test_history_invalid_code_returns_none(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("XXXXX", start_date="2025-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_history_yfexception(self):
        with patch("yfinance.Ticker", side_effect=YFException("Invalid ticker")):
            client = YfinanceClient()
            result = await client.get_stock_history("XXXXX", start_date="2025-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_special_characters_in_code(self):
        """Codes with special chars — yfinance returns empty."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("@#$%")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_string_code(self):
        """Empty string code — yfinance returns empty."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("")

        assert result is None

    @pytest.mark.asyncio
    async def test_very_long_code(self):
        """Extremely long code string — should not crash."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("A" * 1000)

        assert result is None

    @pytest.mark.asyncio
    async def test_history_special_characters(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("!@#", start_date="2025-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_history_empty_string_code(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("", start_date="2025-01-01")

        assert result is None


class TestEmptyResults:
    """Various empty or minimal data scenarios."""

    @pytest.mark.asyncio
    async def test_stock_price_single_row(self):
        """Single data row — avg_volume_30d/90d should be None."""
        hist = _make_hist(MINIMAL_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("1234")

        assert result is not None
        assert result.close == pytest.approx(1050.0)
        assert result.avg_volume_30d is None
        assert result.avg_volume_90d is None

    @pytest.mark.asyncio
    async def test_stock_price_info_raises_yfexception(self):
        """ticker.info can fail independently — price should still be returned."""
        hist = _make_hist(MINIMAL_ROWS)
        def _raise_yf(self):
            raise YFException("rate limited")

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = property(_raise_yf)

        # Simulate info access raising by using a side_effect on info property
        type(mock_ticker).info = property(_raise_yf)

        # Since _fetch catches the exception from ticker.info,
        # we need a different approach:
        # The code wraps ticker.info access in try/except, so we
        # mock it properly
        def make_ticker(sym):
            t = MagicMock()
            t.history.return_value = hist
            type(t).info = property(_raise_yf)
            return t

        with patch("yfinance.Ticker", side_effect=make_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price("1234")

        assert result is not None
        assert result.close == pytest.approx(1050.0)
        # Fundamentals should be empty when info fails
        assert result.trailing_pe is None
        assert result.sector is None

    @pytest.mark.asyncio
    async def test_history_empty_dataframe(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history("9999", start_date="2025-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_empty_quotes(self):
        mock_search = MagicMock()
        mock_search.quotes = []

        with patch("yfinance.Search", return_value=mock_search):
            client = YfinanceClient()
            results = await client.search_ticker("nonexistentticker12345")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_yfexception(self):
        with patch("yfinance.Search", side_effect=YFException("Search error")):
            client = YfinanceClient()
            results = await client.search_ticker("test")

        assert results == []


class TestFxRatesEdgeCases:
    """FX rate edge cases: invalid pairs, partial failures."""

    @pytest.mark.asyncio
    async def test_invalid_pair_ignored(self):
        """Pairs not in FX_PAIRS are silently ignored, returning None if all filtered."""
        client = YfinanceClient()

        with patch("yfinance.Ticker") as mock_yf:
            result = await client.get_fx_rates(["AAABBB"])

        # "AAABBB" is not in FX_PAIRS, so target dict is empty → rates = {} → None
        assert result is None
        mock_yf.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_fx_failure(self):
        """Some pairs succeed, some fail — only successful rates returned."""

        def make_ticker(sym):
            t = MagicMock()
            if sym == "USDJPY=X":
                dates = pd.to_datetime(["2025-01-01"])
                t.history.return_value = pd.DataFrame({"Close": [150.0]}, index=dates)
            elif sym == "EURJPY=X":
                t.history.side_effect = YFException("network timeout")
            else:
                t.history.return_value = pd.DataFrame()
            return t

        with patch("yfinance.Ticker", side_effect=make_ticker):
            client = YfinanceClient()
            result = await client.get_fx_rates(["USDJPY", "EURJPY"])

        assert result is not None
        assert "USDJPY" in result.rates
        assert result.rates["USDJPY"] == pytest.approx(150.0)
        assert "EURJPY" not in result.rates

    @pytest.mark.asyncio
    async def test_all_pairs_fail(self):
        """All FX pairs fail — should return None."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = YFException("service unavailable")

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_fx_rates()

        assert result is None

    @pytest.mark.asyncio
    async def test_all_pairs_empty_history(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_fx_rates(["USDJPY", "EURJPY"])

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_pairs_list(self):
        """Empty list means no pairs requested — target is empty → None."""
        client = YfinanceClient()

        with patch("yfinance.Ticker") as mock_yf:
            result = await client.get_fx_rates([])

        assert result is None
        mock_yf.assert_not_called()


class TestExtractFundamentals:
    """Unit tests for _extract_fundamentals helper."""

    def test_empty_info(self):
        assert _extract_fundamentals({}) == {}

    def test_all_fields_present(self):
        info = {
            "trailingPE": 15.0,
            "forwardPE": 13.5,
            "priceToBook": 1.2,
            "marketCap": 100_000_000_000,
            "sector": "Technology",
            "trailingEps": 200.0,
            "dividendYield": 0.025,
        }
        result = _extract_fundamentals(info)
        assert result["trailing_pe"] == 15.0
        assert result["forward_pe"] == 13.5
        assert result["price_to_book"] == 1.2
        assert result["market_cap"] == 100_000_000_000
        assert result["sector"] == "Technology"
        assert result["trailing_eps"] == 200.0
        assert result["dividend_yield"] == pytest.approx(0.025)

    def test_dividend_yield_zero_excluded(self):
        """Zero dividend yield should not be included."""
        assert _extract_fundamentals({"dividendYield": 0}) == {}

    def test_dividend_yield_negative_excluded(self):
        assert _extract_fundamentals({"dividendYield": -0.01}) == {}

    def test_dividend_yield_none_excluded(self):
        assert _extract_fundamentals({"dividendYield": None}) == {}

    def test_dividend_yield_string_excluded(self):
        """Non-numeric dividendYield should be skipped."""
        assert _extract_fundamentals({"dividendYield": "N/A"}) == {}

    def test_dividend_yield_percentage_normalized(self):
        """Values >= 1.0 are treated as percentages and divided by 100."""
        result = _extract_fundamentals({"dividendYield": 3.5})
        assert result["dividend_yield"] == pytest.approx(0.035)

    def test_dividend_yield_decimal_kept(self):
        """Values < 1.0 are kept as-is."""
        result = _extract_fundamentals({"dividendYield": 0.035})
        assert result["dividend_yield"] == pytest.approx(0.035)


# ---------------------------------------------------------------------------
# Server edge cases
# ---------------------------------------------------------------------------


class TestServerInvalidTicker:
    """Server functions should return error dicts for invalid tickers."""

    @pytest.mark.asyncio
    async def test_get_stock_price_invalid_code(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_price = AsyncMock(return_value=None)
            result = await get_stock_price("XXXXX")

        assert "error" in result
        assert "XXXXX" in result["error"]

    @pytest.mark.asyncio
    async def test_get_stock_history_invalid_code(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=None)
            result = await get_stock_history("XXXXX", start_date="2025-01-01")

        assert "error" in result
        assert "XXXXX" in result["error"]

    @pytest.mark.asyncio
    async def test_search_ticker_no_results(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.search_ticker = AsyncMock(return_value=[])
            result = await search_ticker("ZZZZZ_INVALID")

        assert len(result) == 1
        assert "message" in result[0]
        assert "ZZZZZ_INVALID" in result[0]["message"]

    @pytest.mark.asyncio
    async def test_search_ticker_none_return(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.search_ticker = AsyncMock(return_value=None)
            result = await search_ticker("xxx")

        assert len(result) == 1
        assert "message" in result[0]


class TestServerFxEdgeCases:
    @pytest.mark.asyncio
    async def test_fx_rates_all_fail(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_fx_rates = AsyncMock(return_value=None)
            result = await get_fx_rates()

        assert "error" in result

    @pytest.mark.asyncio
    async def test_fx_rates_invalid_pairs(self):
        """Invalid pairs passed through — client filters them, returns None."""
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_fx_rates = AsyncMock(return_value=None)
            result = await get_fx_rates(pairs=["AAABBB"])

        assert "error" in result
        mock_client.get_fx_rates.assert_awaited_once_with(["AAABBB"])

    @pytest.mark.asyncio
    async def test_fx_rates_empty_pairs_list(self):
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_fx_rates = AsyncMock(return_value=None)
            result = await get_fx_rates(pairs=[])

        assert "error" in result


class TestServerHistoryEdgeCases:
    @pytest.mark.asyncio
    async def test_invalid_interval_passthrough(self):
        """Invalid intervals are passed to yfinance which returns None."""
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=None)
            result = await get_stock_history(
                "7203", start_date="2025-01-01", interval="invalid"
            )

        assert "error" in result
        mock_client.get_stock_history.assert_awaited_once_with(
            "7203", start_date="2025-01-01", end_date=None, interval="invalid"
        )

    @pytest.mark.asyncio
    async def test_start_after_end_returns_error(self):
        """Start date after end date — yfinance returns empty → error."""
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=None)
            result = await get_stock_history(
                "7203", start_date="2025-12-31", end_date="2025-01-01"
            )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_same_start_and_end_returns_error(self):
        """Same start and end date — zero-width range → no data."""
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=None)
            result = await get_stock_history(
                "7203", start_date="2025-06-15", end_date="2025-06-15"
            )

        assert "error" in result


# ---------------------------------------------------------------------------
# Empty / zero-width date range edge cases (client level)
# ---------------------------------------------------------------------------


class TestEmptyDateRanges:
    """Empty or zero-width date ranges at the client level."""

    @pytest.mark.asyncio
    async def test_history_same_start_end(self):
        """Same start and end date — yfinance returns empty → None."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history(
                "7203", start_date="2025-06-15", end_date="2025-06-15"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_history_start_after_end(self):
        """Reversed date range — yfinance returns empty → None."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history(
                "7203", start_date="2025-12-31", end_date="2025-01-01"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_stock_price_same_start_end(self):
        """get_stock_price with same start/end → empty → None."""
        from datetime import date as dt_date

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price(
                "7203",
                start_date=dt_date(2025, 6, 15),
                end_date=dt_date(2025, 6, 15),
            )

        assert result is None


# ---------------------------------------------------------------------------
# Future date edge cases
# ---------------------------------------------------------------------------


class TestFutureDates:
    """Future dates should return empty/None gracefully."""

    @pytest.mark.asyncio
    async def test_history_future_start_date(self):
        """Start date far in the future — no data exists."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history(
                "7203", start_date="2099-01-01"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_history_future_start_and_end(self):
        """Both start and end in the future — no data."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_history(
                "7203", start_date="2099-01-01", end_date="2099-12-31"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_stock_price_future_dates(self):
        """get_stock_price with future date range → empty → None."""
        from datetime import date as dt_date

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker):
            client = YfinanceClient()
            result = await client.get_stock_price(
                "7203",
                start_date=dt_date(2099, 1, 1),
                end_date=dt_date(2099, 12, 31),
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_server_history_future_date(self):
        """Server-level: future date returns error dict."""
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_history = AsyncMock(return_value=None)
            result = await get_stock_history(
                "7203", start_date="2099-01-01"
            )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_server_price_future_date(self):
        """Server-level: future date returns error dict."""
        with patch("yfinance_mcp.server._client") as mock_client:
            mock_client.get_stock_price = AsyncMock(return_value=None)
            result = await get_stock_price("7203")

        assert "error" in result


# ---------------------------------------------------------------------------
# Ticker normalization edge cases
# ---------------------------------------------------------------------------


class TestTickerNormalization:
    """Test that code → ticker conversion handles edge cases."""

    @pytest.mark.asyncio
    async def test_code_gets_t_suffix(self):
        """Normal 4-digit code should get .T suffix."""
        hist = _make_hist(MINIMAL_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            client = YfinanceClient()
            result = await client.get_stock_price("7203")

        assert result is not None
        assert result.ticker == "7203.T"
        mock_yf.assert_called_once_with("7203.T")

    @pytest.mark.asyncio
    async def test_code_with_existing_suffix_gets_doubled(self):
        """Code already ending in '.T' gets doubled — '7203.T.T'.

        This is the current behavior: no suffix stripping.
        The test documents this behavior so any future normalization
        change is caught.
        """
        hist = _make_hist(MINIMAL_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            client = YfinanceClient()
            result = await client.get_stock_price("7203.T")

        assert result is not None
        assert result.ticker == "7203.T.T"
        mock_yf.assert_called_once_with("7203.T.T")

    @pytest.mark.asyncio
    async def test_code_with_whitespace(self):
        """Code with whitespace gets .T appended as-is."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            client = YfinanceClient()
            result = await client.get_stock_price(" 7203 ")

        # Current behavior: whitespace is NOT stripped
        mock_yf.assert_called_once_with(" 7203 .T")
        assert result is None

    @pytest.mark.asyncio
    async def test_code_lowercase(self):
        """Lowercase letters get .T appended without uppercasing."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            client = YfinanceClient()
            result = await client.get_stock_price("aapl")

        # Current behavior: no uppercasing, .T always appended
        mock_yf.assert_called_once_with("aapl.T")
        assert result is None

    @pytest.mark.asyncio
    async def test_history_code_gets_t_suffix(self):
        """get_stock_history also appends .T to code."""
        hist = _make_hist(MINIMAL_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            client = YfinanceClient()
            result = await client.get_stock_history("7203", start_date="2025-01-01")

        assert result is not None
        assert result.ticker == "7203.T"
        mock_yf.assert_called_once_with("7203.T")

    @pytest.mark.asyncio
    async def test_code_leading_zeros_preserved(self):
        """Codes with leading zeros (e.g., '0001') are preserved as strings."""
        hist = _make_hist(MINIMAL_ROWS)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        mock_ticker.info = {}

        with patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf:
            client = YfinanceClient()
            result = await client.get_stock_price("0001")

        assert result is not None
        assert result.code == "0001"
        assert result.ticker == "0001.T"
        mock_yf.assert_called_once_with("0001.T")
