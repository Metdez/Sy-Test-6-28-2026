import os
import tempfile
from pathlib import Path
from symphony.config import build_config, ConfigError


def test_defaults_applied():
    cfg = build_config({
        "tracker": {"kind": "linear", "api_key": "key123", "project_slug": "my-proj"}
    })
    assert cfg.poll_interval_ms == 30000
    assert cfg.max_concurrent_agents == 10
    assert cfg.max_turns == 20
    assert cfg.max_retry_backoff_ms == 300000
    assert cfg.codex_command == "codex app-server"
    assert cfg.codex_turn_timeout_ms == 3600000
    assert cfg.codex_read_timeout_ms == 5000
    assert cfg.codex_stall_timeout_ms == 300000
    assert cfg.tracker_active_states == ["Todo", "In Progress"]
    assert cfg.tracker_terminal_states == ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]
    assert cfg.tracker_required_labels == []
    assert cfg.max_concurrent_agents_by_state == {}
    assert cfg.server_port is None


def test_env_var_indirection(monkeypatch):
    monkeypatch.setenv("MY_LINEAR_KEY", "resolved_key")
    cfg = build_config({
        "tracker": {"kind": "linear", "api_key": "$MY_LINEAR_KEY", "project_slug": "p"}
    })
    assert cfg.tracker_api_key == "resolved_key"


def test_env_var_missing_raises(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    import pytest
    with pytest.raises(ConfigError, match="MISSING_VAR"):
        build_config({
            "tracker": {"kind": "linear", "api_key": "$MISSING_VAR", "project_slug": "p"}
        })


def test_tilde_expansion():
    cfg = build_config({
        "tracker": {"kind": "linear", "api_key": "k", "project_slug": "p"},
        "workspace": {"root": "~/my_workspaces"},
    })
    assert cfg.workspace_root == str(Path("~/my_workspaces").expanduser())
    assert not cfg.workspace_root.startswith("~")


def test_workspace_root_absolute():
    cfg = build_config({
        "tracker": {"kind": "linear", "api_key": "k", "project_slug": "p"},
        "workspace": {"root": "/tmp/wk"},
    })
    assert Path(cfg.workspace_root).is_absolute()


def test_missing_project_slug_raises():
    import pytest
    with pytest.raises(ConfigError, match="project_slug"):
        build_config({"tracker": {"kind": "linear", "api_key": "k"}})


def test_per_state_concurrency():
    cfg = build_config({
        "tracker": {"kind": "linear", "api_key": "k", "project_slug": "p"},
        "agent": {"max_concurrent_agents_by_state": {"In Progress": 2}},
    })
    assert cfg.max_concurrent_agents_by_state == {"In Progress": 2}
