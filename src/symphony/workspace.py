"""Workspace manager — per-issue dirs, hook execution, safety invariants (PRD §3.1.5, §8)."""
from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

from symphony.config import ServiceConfig
from symphony.types import Issue, Workspace


class WorkspaceError(Exception):
    pass


def _sanitize_key(identifier: str) -> str:
    """Produce a safe directory name from an issue identifier."""
    safe = re.sub(r"[^\w\-]", "_", identifier)
    # Guard against path traversal
    safe = safe.strip("._/\\")
    return safe or "issue"


def workspace_path(issue_identifier: str, root: str) -> str:
    key = _sanitize_key(issue_identifier)
    return str(Path(root) / key)


async def run_hook(script: str, ws_path: str, timeout_ms: int) -> None:
    timeout_s = timeout_ms / 1000.0
    proc = await asyncio.create_subprocess_shell(
        script,
        cwd=ws_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        raise WorkspaceError(f"Hook timed out after {timeout_ms}ms: {script!r}")
    if proc.returncode != 0:
        raise WorkspaceError(f"Hook exited {proc.returncode}: {script!r}")


async def ensure_workspace(issue: Issue, config: ServiceConfig) -> Workspace:
    ws_path = workspace_path(issue.identifier, config.workspace_root)
    target = Path(ws_path)

    created_now = False
    if target.exists():
        if not target.is_dir():
            raise WorkspaceError(f"Workspace path exists but is not a directory: {ws_path}")
    else:
        target.mkdir(parents=True, exist_ok=True)
        created_now = True

    key = _sanitize_key(issue.identifier)
    ws = Workspace(path=ws_path, workspace_key=key, created_now=created_now)

    if created_now and config.hook_after_create:
        await run_hook(config.hook_after_create, ws_path, config.hook_timeout_ms)

    return ws


async def remove_workspace(issue: Issue, config: ServiceConfig) -> None:
    ws_path = workspace_path(issue.identifier, config.workspace_root)
    target = Path(ws_path)
    if not target.exists():
        return
    if config.hook_before_remove:
        await run_hook(config.hook_before_remove, ws_path, config.hook_timeout_ms)
    shutil.rmtree(ws_path, ignore_errors=True)
