import asyncio
import os
import sys
from pathlib import Path
import pytest
from symphony.config import build_config
from symphony.types import Issue
from symphony.workspace import workspace_path, ensure_workspace, WorkspaceError

BASE_ISSUE = Issue(id="abc", identifier="PRJ-1", title="Fix bug", state="Todo")


def make_config(root: str) -> object:
    return build_config({
        "tracker": {"kind": "linear", "api_key": "k", "project_slug": "p"},
        "workspace": {"root": root},
    })


def test_workspace_path_deterministic(tmp_path):
    root = str(tmp_path)
    p1 = workspace_path("PRJ-1", root)
    p2 = workspace_path("PRJ-1", root)
    assert p1 == p2


def test_workspace_path_sanitized(tmp_path):
    root = str(tmp_path)
    path = workspace_path("PRJ-1", root)
    # Must be under root
    assert path.startswith(root)
    # Sanitized — no path traversal
    path2 = workspace_path("../evil", root)
    assert ".." not in path2
    assert path2.startswith(root)


def test_workspace_path_different_issues(tmp_path):
    root = str(tmp_path)
    assert workspace_path("PRJ-1", root) != workspace_path("PRJ-2", root)


@pytest.mark.asyncio
async def test_ensure_workspace_creates_dir(tmp_path):
    cfg = make_config(str(tmp_path))
    ws = await ensure_workspace(BASE_ISSUE, cfg)
    assert Path(ws.path).is_dir()
    assert ws.created_now is True


@pytest.mark.asyncio
async def test_ensure_workspace_existing_dir(tmp_path):
    cfg = make_config(str(tmp_path))
    ws1 = await ensure_workspace(BASE_ISSUE, cfg)
    ws2 = await ensure_workspace(BASE_ISSUE, cfg)
    assert ws1.path == ws2.path
    assert ws2.created_now is False  # already existed


@pytest.mark.asyncio
async def test_ensure_workspace_file_collision_raises(tmp_path):
    cfg = make_config(str(tmp_path))
    # Place a file where the directory should go
    expected = workspace_path(BASE_ISSUE.identifier, str(tmp_path))
    Path(expected).write_text("oops")
    with pytest.raises(WorkspaceError, match="not a directory"):
        await ensure_workspace(BASE_ISSUE, cfg)
