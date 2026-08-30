"""Tests for Claude Code zero-config quota discovery."""

import json
import time
from unittest.mock import patch

from cclimits import (
    _claude_desktop_dir_candidates,
    _claude_desktop_tokens,
    get_claude_cached_usage,
    get_claude_usage,
)


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



def test_desktop_oauth_wins_over_local_usage_cache():
    desktop = {
        "access_token": "desktop-token",
        "subscription_type": "pro",
        "source_path": "C:/Users/test/AppData/Roaming/Claude/config.json",
    }
    with patch("cclimits.get_claude_credentials", return_value=None), \
         patch("cclimits.get_claude_desktop_credentials", return_value=desktop), \
         patch("cclimits.get_claude_cached_usage") as cached, \
         patch("cclimits.http_get", return_value=(200, {
             "five_hour": {"utilization": 18.0},
             "seven_day": {"utilization": 42.0},
         })) as http_get:
        result = get_claude_usage()

    assert result["status"] == "ok"
    assert result["source"] == "claude_desktop_oauth"
    assert result["plan"] == "pro"
    assert result["five_hour"]["remaining"] == "82.0%"
    assert result["seven_day"]["remaining"] == "58.0%"
    cached.assert_not_called()
    headers = http_get.call_args.args[1]
    assert headers["Authorization"] == "Bearer desktop-token"


def test_claude_code_oauth_still_precedes_desktop():
    with patch("cclimits.get_claude_credentials", return_value="cli-token"), \
         patch("cclimits.get_claude_desktop_credentials") as desktop, \
         patch("cclimits.http_get", return_value=(200, {
             "five_hour": {"utilization": 7.0},
         })):
        result = get_claude_usage()

    assert result["source"] == "claude_code_oauth"
    desktop.assert_not_called()


def test_parses_desktop_token_cache_read_only(tmp_path):
    profile = tmp_path / "Claude"
    profile.mkdir()
    (profile / "config.json").write_text(json.dumps({
        "oauth:tokenCacheV2": "encrypted-placeholder",
    }))

    decrypted = json.dumps({
        "9d1c250a-e61b-44d9-88ed-5944d1962f5e:00000000-0000-0000-0000-000000000000:"
        "https://api.anthropic.com:user:profile user:inference": {
            "token": "desktop-live-token",
            "expiresAt": (time.time() + 3600) * 1000,
            "subscriptionType": "pro",
        }
    }).encode()

    with patch("cclimits.sys.platform", "win32"), \
         patch("cclimits._claude_desktop_dir_candidates", return_value=[profile]), \
         patch("cclimits._claude_desktop_safestorage_key", return_value=b"k" * 32), \
         patch("cclimits._claude_desktop_decrypt", return_value=decrypted):
        tokens = _claude_desktop_tokens()

    assert len(tokens) == 1
    assert tokens[0]["access_token"] == "desktop-live-token"
    assert tokens[0]["subscription_type"] == "pro"
    assert "refresh_token" not in tokens[0]
    assert tokens[0]["source"] == "claude_desktop_oauth"


def test_ignores_expired_desktop_token(tmp_path):
    profile = tmp_path / "Claude"
    profile.mkdir()
    (profile / "config.json").write_text(json.dumps({
        "oauth:tokenCacheV2": "encrypted-placeholder",
    }))

    decrypted = json.dumps({
        "9d1c250a-e61b-44d9-88ed-5944d1962f5e:00000000-0000-0000-0000-000000000000:"
        "https://api.anthropic.com:user:profile user:inference": {
            "token": "expired-token",
            "expiresAt": (time.time() - 60) * 1000,
        }
    }).encode()

    with patch("cclimits.sys.platform", "win32"), \
         patch("cclimits._claude_desktop_dir_candidates", return_value=[profile]), \
         patch("cclimits._claude_desktop_safestorage_key", return_value=b"k" * 32), \
         patch("cclimits._claude_desktop_decrypt", return_value=decrypted):
        assert _claude_desktop_tokens() == []


def test_windows_desktop_discovery_includes_msix_profile(tmp_path):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    standard = roaming / "Claude"
    standard.mkdir(parents=True)

    msix = local / "Packages" / "Claude_test" / "LocalCache" / "Roaming" / "Claude"
    (msix / "Network").mkdir(parents=True)
    (msix / "Network" / "Cookies").write_text("fixture")

    with patch("cclimits.sys.platform", "win32"), \
         patch.dict(
             "cclimits.os.environ",
             {"APPDATA": str(roaming), "LOCALAPPDATA": str(local)},
             clear=True,
         ):
        dirs = _claude_desktop_dir_candidates()

    assert dirs[0] == standard
    assert msix in dirs
