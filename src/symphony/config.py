"""Config layer — typed getters, defaults, env resolution (PRD §3.1.2, §6.4)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


class ServiceConfig:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # tracker
    @property
    def tracker_kind(self) -> str:
        return self._data["tracker"]["kind"]

    @property
    def tracker_endpoint(self) -> str:
        return self._data["tracker"].get("endpoint", "https://api.linear.app/graphql")

    @property
    def tracker_api_key(self) -> str:
        return self._data["tracker"]["api_key"]

    @property
    def tracker_project_slug(self) -> str:
        return self._data["tracker"]["project_slug"]

    @property
    def tracker_required_labels(self) -> list[str]:
        return self._data["tracker"].get("required_labels", [])

    @property
    def tracker_active_states(self) -> list[str]:
        return self._data["tracker"].get("active_states", ["Todo", "In Progress"])

    @property
    def tracker_terminal_states(self) -> list[str]:
        return self._data["tracker"].get(
            "terminal_states", ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]
        )

    # polling
    @property
    def poll_interval_ms(self) -> int:
        return self._data.get("polling", {}).get("interval_ms", 30000)

    # workspace
    @property
    def workspace_root(self) -> str:
        return self._data["workspace"]["root"]

    # hooks
    @property
    def hook_after_create(self) -> str | None:
        return self._data.get("hooks", {}).get("after_create")

    @property
    def hook_before_run(self) -> str | None:
        return self._data.get("hooks", {}).get("before_run")

    @property
    def hook_after_run(self) -> str | None:
        return self._data.get("hooks", {}).get("after_run")

    @property
    def hook_before_remove(self) -> str | None:
        return self._data.get("hooks", {}).get("before_remove")

    @property
    def hook_timeout_ms(self) -> int:
        return self._data.get("hooks", {}).get("timeout_ms", 60000)

    # agent
    @property
    def max_concurrent_agents(self) -> int:
        return self._data.get("agent", {}).get("max_concurrent_agents", 10)

    @property
    def max_turns(self) -> int:
        return self._data.get("agent", {}).get("max_turns", 20)

    @property
    def max_retry_backoff_ms(self) -> int:
        return self._data.get("agent", {}).get("max_retry_backoff_ms", 300000)

    @property
    def max_concurrent_agents_by_state(self) -> dict[str, int]:
        return self._data.get("agent", {}).get("max_concurrent_agents_by_state", {})

    # codex
    @property
    def codex_command(self) -> str:
        return self._data.get("codex", {}).get("command", "codex app-server")

    @property
    def codex_turn_timeout_ms(self) -> int:
        return self._data.get("codex", {}).get("turn_timeout_ms", 3600000)

    @property
    def codex_read_timeout_ms(self) -> int:
        return self._data.get("codex", {}).get("read_timeout_ms", 5000)

    @property
    def codex_stall_timeout_ms(self) -> int:
        return self._data.get("codex", {}).get("stall_timeout_ms", 300000)

    # server
    @property
    def server_port(self) -> int | None:
        return self._data.get("server", {}).get("port")


def _resolve_api_key(raw_key: str) -> str:
    if raw_key.startswith("$"):
        var_name = raw_key[1:]
        value = os.environ.get(var_name)
        if value is None:
            raise ConfigError(f"Env var '{var_name}' required for tracker.api_key but not set")
        return value
    return raw_key


def _resolve_workspace_root(raw_path: str | None) -> str:
    if raw_path is None:
        return str(Path(tempfile.gettempdir()) / "symphony_workspaces")
    return str(Path(raw_path).expanduser().resolve())


def build_config(raw: dict[str, Any]) -> ServiceConfig:
    tracker = raw.get("tracker", {})

    if "project_slug" not in tracker:
        raise ConfigError("tracker.project_slug is required")

    # Resolve $VAR for api_key
    raw_key = tracker.get("api_key", "")
    tracker = {**tracker, "api_key": _resolve_api_key(raw_key)}

    # Resolve workspace root
    ws_root = raw.get("workspace", {}).get("root")
    workspace = {**raw.get("workspace", {}), "root": _resolve_workspace_root(ws_root)}

    resolved = {**raw, "tracker": tracker, "workspace": workspace}
    return ServiceConfig(resolved)
