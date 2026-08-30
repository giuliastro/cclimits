"""Tests for Claude Code zero-config quota discovery."""

import json
import time
from unittest.mock import patch

from cclimits import get_claude_cached_usage, get_claude_usage


def test_reads_claude_code_cached_usage_without_credentials(tmp_path):
    state = tmp_path / ".claude.json"
    state.write_text(json.dumps({
        "cachedUsageUtilization": {
            "fetchedAtMs": int(time.time() * 1000),
            "accountUuid": "account-123",
            "utilization": {
                "five_hour": {
                    "utilization": 37.5,
                    "resets_at": "2099-01-01T12:00:00+00:00",
                },
                "seven_day": {
                    "utilization": 61,
                    "resets_at": "2099-01-07T12:00:00+00:00",
                },
                "seven_day_opus": None,
            },
        }
    }))

    with patch("cclimits.Path.home", return_value=tmp_path), \
         patch.dict("cclimits.os.environ", {}, clear=True):
        result = get_claude_cached_usage()

    assert result is not None
    assert result["status"] == "ok"
    assert result["source"] == "claude_code_cache"
    assert result["source_path"] == str(state)
    assert result["account_uuid"] == "account-123"
    assert result["five_hour"]["used"] == "37.5%"
    assert result["five_hour"]["remaining"] == "62.5%"
    assert result["seven_day"]["used"] == "61.0%"
    assert result["seven_day"]["remaining"] == "39.0%"
    assert result["source_age_seconds"] < 5
    assert "source_stale" not in result


def test_marks_old_claude_code_snapshot_stale(tmp_path):
    state = tmp_path / ".claude.json"
    state.write_text(json.dumps({
        "cachedUsageUtilization": {
            "fetchedAtMs": int((time.time() - 7200) * 1000),
            "utilization": {
                "five_hour": {"utilization": 10},
            },
        }
    }))

    with patch("cclimits.Path.home", return_value=tmp_path), \
         patch.dict("cclimits.os.environ", {}, clear=True):
        result = get_claude_cached_usage()

    assert result is not None
    assert result["source_stale"] is True
    assert result["source_age_seconds"] >= 7190


def test_no_oauth_credentials_falls_back_to_claude_code_cache():
    cached = {
        "status": "ok",
        "source": "claude_code_cache",
        "five_hour": {"used": "12.0%", "remaining": "88.0%"},
    }
    with patch("cclimits.get_claude_credentials", return_value=None), \
         patch("cclimits.get_claude_cached_usage", return_value=cached), \
         patch("cclimits.http_get") as http_get:
        result = get_claude_usage()

    assert result == cached
    http_get.assert_not_called()


def test_live_oauth_still_wins_when_available():
    with patch("cclimits.get_claude_credentials", return_value="token"), \
         patch("cclimits.get_claude_cached_usage") as cached, \
         patch("cclimits.http_get", return_value=(200, {
             "five_hour": {"utilization": 25.0},
         })):
        result = get_claude_usage()

    assert result["status"] == "ok"
    assert result["five_hour"]["used"] == "25.0%"
    cached.assert_not_called()
