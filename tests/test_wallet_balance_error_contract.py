#!/usr/bin/env python3
"""Test the wallet balance CLI error contract — every failure path produces a distinct exit code.

Exit codes (documented in --help):
  0 = success
  1 = usage / input error
  2 = network / connectivity error
  3 = bad / unexpected response from server
  4 = wallet not found
  5 = authentication / decryption failure
  6 = unexpected internal error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

# Add the tools directory to the path so we can import the wallet CLI
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from rustchain_wallet_cli import (
    EXIT_SUCCESS,
    EXIT_NETWORK_ERROR,
    EXIT_BAD_RESPONSE,
    EXIT_WALLET_NOT_FOUND,
    cmd_balance,
)


# ============================================================
# Helpers
# ============================================================

class FakeArgs:
    """Minimal argparse.Namespace stand-in."""
    def __init__(self, wallet_id: str):
        self.wallet_id = wallet_id


class FakeResponse:
    """Simulate a requests.Response."""
    def __init__(self, status_code: int, json_data, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._json_data is None:
            raise json.JSONDecodeError("No JSON", self.text, 0)
        return self._json_data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ============================================================
# Tests
# ============================================================

@patch("rustchain_wallet_cli.requests.get")
def test_balance_success(mock_get):
    """Happy path: server returns valid balance."""
    mock_get.return_value = FakeResponse(
        200, {"amount_rtc": 42.5, "nonce": 7}
    )
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_SUCCESS, f"Expected 0, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_network_error(mock_get):
    """Network error (e.g. DNS failure, connection refused) → exit code 2."""
    mock_get.side_effect = requests.exceptions.ConnectionError("DNS resolution failed")
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_NETWORK_ERROR, f"Expected {EXIT_NETWORK_ERROR}, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_timeout(mock_get):
    """Request timeout → exit code 2."""
    mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_NETWORK_ERROR, f"Expected {EXIT_NETWORK_ERROR}, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_wallet_not_found_404(mock_get):
    """Server returns 404 → exit code 4 (wallet not found)."""
    mock_get.return_value = FakeResponse(404, None, text="Not Found")
    rc = cmd_balance(FakeArgs("RTCnonexistent"))
    assert rc == EXIT_WALLET_NOT_FOUND, f"Expected {EXIT_WALLET_NOT_FOUND}, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_server_error_500(mock_get):
    """Server returns 500 → exit code 3 (bad response)."""
    mock_get.return_value = FakeResponse(500, {"error": "internal"})
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_BAD_RESPONSE, f"Expected {EXIT_BAD_RESPONSE}, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_malformed_json(mock_get):
    """Server returns non-JSON body (e.g. HTML error page) → exit code 3."""
    mock_get.return_value = FakeResponse(200, None, text="<html>Server Error</html>")
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_BAD_RESPONSE, f"Expected {EXIT_BAD_RESPONSE}, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_missing_amount_field(mock_get):
    """Server returns JSON without amount_rtc → exit code 3."""
    mock_get.return_value = FakeResponse(200, {"nonce": 7})
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_BAD_RESPONSE, f"Expected {EXIT_BAD_RESPONSE}, got {rc}"


@patch("rustchain_wallet_cli.requests.get")
def test_balance_balance_rtc_alias(mock_get):
    """Server returns balance_rtc instead of amount_rtc → success (alias fallback)."""
    mock_get.return_value = FakeResponse(200, {"balance_rtc": 100.0, "nonce": 3})
    rc = cmd_balance(FakeArgs("RTCabc123"))
    assert rc == EXIT_SUCCESS, f"Expected 0, got {rc}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])