"""Tests for zero-config OpenCode Go quota discovery."""

import json
import sqlite3
from unittest.mock import patch

from cclimits import (
    OPENCODE_GO_NO_SUB_ERROR,
    _extract_opencode_go_credential,
    _normalize_opencode_go_window,
    _opencode_auth_paths,
    get_opencode_go_credentials,
    get_opencode_go_usage,
    print_oneline,
)


def test_extracts_native_opencode_go_api_key():
    result = _extract_opencode_go_credential({
        "opencode-go": {"type": "api", "key": "go-key"},
        "openai": {"type": "oauth", "access": "ignore"},
    })
    assert result == ("go-key", "opencode-go")


def test_native_go_entry_precedes_generic_opencode_key():
    result = _extract_opencode_go_credential({
        "opencode": {"type": "api", "key": "zen-key"},
        "opencode-go": {"type": "api", "key": "go-key"},
    })
    assert result == ("go-key", "opencode-go")


def test_oauth_entry_is_not_misused_as_go_api_key():
    assert _extract_opencode_go_credential({
        "opencode-go": {"type": "oauth", "access": "oauth-token", "refresh": "refresh"},
    }) is None


def test_reads_existing_opencode_auth_json_zero_config(tmp_path):
    auth = tmp_path / "opencode" / "auth.json"
    auth.parent.mkdir()
    auth.write_text(json.dumps({
        "opencode-go": {"type": "api", "key": "existing-go-key"},
    }))

    with patch.dict("cclimits.os.environ", {"XDG_DATA_HOME": str(tmp_path)}, clear=True):
        result = get_opencode_go_credentials()

    assert result is not None
    assert result["key"] == "existing-go-key"
    assert result["provider_id"] == "opencode-go"
    assert result["source"] == "OpenCode auth.json"
    assert str(tmp_path) not in result["source"]


def test_reads_pi_auth_json_for_existing_zen_key(tmp_path):
    agent = tmp_path / "pi-agent"
    agent.mkdir()
    (agent / "auth.json").write_text(json.dumps({
        "opencode": {"type": "api_key", "key": "existing-zen-key"},
    }))

    with patch.dict("cclimits.os.environ", {"PI_CODING_AGENT_DIR": str(agent)}, clear=True), \
         patch("cclimits.Path.home", return_value=tmp_path / "home"):
        result = get_opencode_go_credentials()

    assert result == {
        "key": "existing-zen-key",
        "source": "Pi auth.json",
        "provider_id": "opencode",
    }


def test_reads_omp_agent_db_read_only_for_existing_zen_key(tmp_path):
    home = tmp_path / "home"
    db = home / ".omp" / "agent" / "agent.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE auth_credentials (id INTEGER PRIMARY KEY, provider TEXT, credential_type TEXT, data TEXT, disabled_cause TEXT)"
    )
    conn.execute(
        "INSERT INTO auth_credentials(provider, credential_type, data, disabled_cause) VALUES (?, ?, ?, NULL)",
        ("opencode-zen", "api_key", json.dumps({"key": "existing-zen-key"})),
    )
    conn.commit()
    conn.close()
    before = db.stat().st_mtime_ns

    with patch.dict("cclimits.os.environ", {}, clear=True), \
         patch("cclimits.Path.home", return_value=home):
        result = get_opencode_go_credentials()

    assert result == {
        "key": "existing-zen-key",
        "source": "OMP agent.db",
        "provider_id": "opencode-zen",
    }
    assert before == db.stat().st_mtime_ns


def test_env_key_precedes_disk(tmp_path):
    auth = tmp_path / "opencode" / "auth.json"
    auth.parent.mkdir()
    auth.write_text(json.dumps({
        "opencode-go": {"type": "api", "key": "disk-key"},
    }))

    with patch.dict(
        "cclimits.os.environ",
        {"XDG_DATA_HOME": str(tmp_path), "OPENCODE_API_KEY": "env-key"},
        clear=True,
    ):
        result = get_opencode_go_credentials()

    assert result is not None
    assert result["key"] == "env-key"
    assert result["source"] == "$OPENCODE_API_KEY"


def test_xdg_path_is_first_when_configured(tmp_path):
    with patch.dict("cclimits.os.environ", {"XDG_DATA_HOME": str(tmp_path)}, clear=True):
        paths = _opencode_auth_paths()
    assert paths[0] == tmp_path / "opencode" / "auth.json"


def test_normalizes_percent_and_reset():
    window = _normalize_opencode_go_window({
        "percent": 27.5,
        "resetsAt": "2099-01-01T00:00:00Z",
        "windowSeconds": 18000,
    }, "5h")

    assert window is not None
    assert window["used"] == "27.5%"
    assert window["remaining"] == "72.5%"
    assert window["window"] == "5h"
    assert window["window_seconds"] == 18000
    assert window["resets_at"] == "2099-01-01T00:00:00Z"


@patch("cclimits.get_opencode_go_credentials")
@patch("cclimits.http_get")
def test_fetches_authoritative_go_windows(mock_get, mock_creds):
    mock_creds.return_value = {
        "key": "go-key",
        "source": "OpenCode auth.json",
        "provider_id": "opencode-go",
    }
    mock_get.return_value = (200, {
        "plan": "Go",
        "usage": {
            "rolling": {
                "percent": 10,
                "resetsAt": "2099-01-01T00:00:00Z",
                "windowSeconds": 18000,
            },
            "weekly": {
                "percent": 35,
                "resetsAt": "2099-01-07T00:00:00Z",
            },
            "monthly": {
                "percent": 50,
                "resetsAt": "2099-02-01T00:00:00Z",
            },
        },
    })

    result = get_opencode_go_usage()

    assert result["status"] == "ok"
    assert result["source"] == "opencode_go_api"
    assert result["auth"] == "OpenCode auth.json"
    assert "/home/test" not in json.dumps(result)
    assert result["plan"] == "Go"
    assert result["primary_window"]["used"] == "10.0%"
    assert result["primary_window"]["remaining"] == "90.0%"
    assert result["secondary_window"]["used"] == "35.0%"
    assert result["monthly_window"]["used"] == "50.0%"

    url, headers = mock_get.call_args.args
    assert url == "https://opencode.ai/zen/go/v1/usage"
    assert headers["Authorization"] == "Bearer go-key"


@patch("cclimits.get_opencode_go_credentials")
def test_no_credentials_never_initiates_login(mock_creds):
    mock_creds.return_value = None
    result = get_opencode_go_usage()
    assert result["error"] == "No credentials found"
    assert "reuse its existing auth.json" in result["hint"]


@patch("cclimits.get_opencode_go_credentials")
@patch("cclimits.http_get")
def test_403_is_no_go_entitlement(mock_get, mock_creds):
    mock_creds.return_value = {
        "key": "zen-only-key",
        "source": "auth.json",
        "provider_id": "opencode",
    }
    mock_get.return_value = (403, {"error": "EntitlementError"})

    result = get_opencode_go_usage()

    assert result["error"] == OPENCODE_GO_NO_SUB_ERROR


def test_oneline_explains_missing_go_entitlement(capsys):
    print_oneline(
        {"opencode_go": {"error": OPENCODE_GO_NO_SUB_ERROR}},
        window="both",
        show_resets=True,
    )

    assert capsys.readouterr().out.strip() == "OpenCode Go: no subscription"
