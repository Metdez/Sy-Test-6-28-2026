"""Codex app-server runner — launch, prompt build, turn loop (PRD §3.1.6, §10)."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from symphony.config import ServiceConfig
from symphony.types import Issue, LiveSession, Workspace


class AgentError(Exception):
    """Raised when the Codex app-server client encounters a fatal error."""

    def __init__(self, category: str, message: str) -> None:
        self.category = category
        super().__init__(f"{category}: {message}")


def build_prompt(template: str, issue: Issue, attempt: int | None) -> str:
    """Render prompt_template with issue context (PRD §10, §12)."""
    result = template
    result = result.replace("{{issue.id}}", issue.id)
    result = result.replace("{{issue.identifier}}", issue.identifier)
    result = result.replace("{{issue.title}}", issue.title)
    result = result.replace("{{issue.description}}", issue.description or "")
    result = result.replace("{{issue.state}}", issue.state)
    result = result.replace(
        "{{issue.priority}}", str(issue.priority) if issue.priority is not None else ""
    )
    result = result.replace("{{attempt}}", str(attempt) if attempt is not None else "0")
    return result


class AgentRunner:
    """Manages the lifecycle of a Codex app-server subprocess for one issue run."""

    async def run(
        self,
        issue: Issue,
        workspace: Workspace,
        prompt: str,
        config: ServiceConfig,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> LiveSession:
        command = config.codex_command
        turn_timeout_s = config.codex_turn_timeout_ms / 1000.0

        try:
            proc = await asyncio.create_subprocess_shell(
                f"bash -lc {json.dumps(command)}",
                cwd=workspace.path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise AgentError("codex_not_found", str(e)) from e

        if proc.stdin is None or proc.stdout is None:
            proc.kill()
            raise AgentError("codex_not_found", "Failed to open subprocess pipes")

        # Minimal session bootstrap — real implementation sends protocol messages
        thread_id = f"thread-{issue.id}"
        turn_id = "turn-0"
        session = LiveSession(
            session_id=f"{thread_id}-{turn_id}",
            thread_id=thread_id,
            turn_id=turn_id,
        )

        await on_event(
            {"event": "session_started", "timestamp": datetime.now(UTC).isoformat()}
        )

        # Send prompt as first turn input
        try:
            proc.stdin.write((prompt + "\n").encode())
            await proc.stdin.drain()
            proc.stdin.close()
        except BrokenPipeError as e:
            raise AgentError("port_exit", "Codex process closed stdin") from e

        # Drain stdout with turn timeout
        try:
            await asyncio.wait_for(proc.communicate(), timeout=turn_timeout_s)
        except TimeoutError:
            proc.kill()
            raise AgentError("turn_timeout", f"Turn exceeded {config.codex_turn_timeout_ms}ms")

        if proc.returncode != 0:
            raise AgentError("turn_failed", f"Codex exited with code {proc.returncode}")

        await on_event(
            {"event": "turn_completed", "timestamp": datetime.now(UTC).isoformat()}
        )

        session.turn_id = "turn-1"
        session.session_id = f"{thread_id}-turn-1"
        session.turn_count = 1

        return session
