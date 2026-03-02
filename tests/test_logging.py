"""Tests for logging architecture: library-safe, no stdout pollution."""

from __future__ import annotations

import logging

import pytest


class TestLibraryLogging:
    """Library modules must use stdlib logging with NullHandler."""

    def test_import_produces_no_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Importing yfinance_mcp must not print anything to stdout."""
        import importlib

        importlib.reload(__import__("yfinance_mcp"))
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_null_handler_configured(self) -> None:
        """yfinance_mcp logger must have NullHandler to prevent 'No handlers' warning."""
        lgr = logging.getLogger("yfinance_mcp")
        handler_types = [type(h) for h in lgr.handlers]
        assert logging.NullHandler in handler_types

    def test_client_uses_stdlib_logging(self) -> None:
        """client module must use stdlib logging, not loguru."""
        from yfinance_mcp import client

        mod_logger = getattr(client, "logger", None)
        assert mod_logger is not None, "client has no logger"
        assert isinstance(mod_logger, logging.Logger), (
            f"client.logger is {type(mod_logger).__name__}, expected logging.Logger"
        )
