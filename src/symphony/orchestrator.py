"""Orchestrator — poll loop, dispatch, reconcile, retry (PRD §3.1.4, §7, §16)."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from symphony.agent import AgentError, AgentRunner, build_prompt
from symphony.config import ServiceConfig
from symphony.log import get_logger
from symphony.tracker.linear import fetch_candidate_issues, fetch_issue_states_by_ids
from symphony.types import (
    Issue,
    OrchestratorRuntimeState,
    RetryEntry,
    RunAttempt,
    RunAttemptStatus,
    RunningEntry,
    WorkflowDefinition,
)
from symphony.workspace import ensure_workspace

log = get_logger()

_BASE_BACKOFF_MS = 5_000


def _sort_issues(issues: list[Issue]) -> list[Issue]:
    """Sort by priority (lower int = higher priority), then oldest created_at first (PRD §16.2)."""
    def key(i: Issue) -> tuple[int, float]:
        p = i.priority if i.priority is not None else 999
        ts = i.created_at.timestamp() if i.created_at else float("inf")
        return (p, ts)
    return sorted(issues, key=key)


def _backoff_ms(attempt: int, max_ms: int) -> int:
    """Exponential backoff with cap (PRD §16.6)."""
    raw = _BASE_BACKOFF_MS * (2 ** (attempt - 1))
    return min(int(raw), max_ms)


class Orchestrator:
    def __init__(self, config: ServiceConfig, workflow: WorkflowDefinition) -> None:
        self.config = config
        self.workflow = workflow
        self.state = OrchestratorRuntimeState(
            poll_interval_ms=config.poll_interval_ms,
            max_concurrent_agents=config.max_concurrent_agents,
        )
        self._shutdown = asyncio.Event()
        self._runner = AgentRunner()

    async def startup(self) -> None:
        log.info("symphony.startup", version="0.1.0")

    async def run_forever(self) -> None:
        await self.startup()
        while not self._shutdown.is_set():
            try:
                await self._poll_tick()
            except Exception as exc:
                log.error("symphony.poll_tick.error", error=str(exc))
            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.config.poll_interval_ms / 1000.0,
                )
            except TimeoutError:
                pass

    async def shutdown(self) -> None:
        log.info("symphony.shutdown")
        self._shutdown.set()

    async def _poll_tick(self) -> None:
        await self._reconcile_active_runs()
        issues = await fetch_candidate_issues(self.config)
        issues = _sort_issues(issues)
        await self._dispatch_eligible(issues, self._dispatch_one)

    async def _reconcile_active_runs(self) -> None:
        if not self.state.running:
            return
        running_ids = list(self.state.running.keys())
        try:
            states = await fetch_issue_states_by_ids(running_ids, self.config)
        except Exception as exc:
            log.warning("symphony.reconcile.error", error=str(exc))
            return

        terminal = set(self.config.tracker_terminal_states)
        active = set(self.config.tracker_active_states)
        for issue_id, state_name in states.items():
            if state_name in terminal or state_name not in active:
                log.info("symphony.reconcile.stop", issue_id=issue_id, state=state_name)
                self._release(issue_id)

    async def _dispatch_eligible(
        self,
        issues: list[Issue],
        dispatch_fn: Callable[[Issue], Awaitable[None]],
    ) -> None:
        for issue in issues:
            free = self.config.max_concurrent_agents - len(self.state.running)
            if free <= 0:
                break
            if issue.id in self.state.claimed:
                continue
            if self._is_blocked(issue):
                continue
            await dispatch_fn(issue)

    def _is_blocked(self, issue: Issue) -> bool:
        todo_states = {"Todo"}
        for blocker in issue.blocked_by:
            if blocker.state and blocker.state not in todo_states:
                return True
        return False

    async def _dispatch_one(self, issue: Issue) -> None:
        log.info("symphony.dispatch", issue_id=issue.id, identifier=issue.identifier)
        self.state.claimed.add(issue.id)
        attempt = RunAttempt(
            issue_id=issue.id,
            issue_identifier=issue.identifier,
            workspace_path="",
            started_at=datetime.now(UTC),
            status=RunAttemptStatus.PREPARING_WORKSPACE,
        )
        entry = RunningEntry(
            issue_id=issue.id,
            issue_identifier=issue.identifier,
            attempt=attempt,
        )
        self.state.running[issue.id] = entry
        asyncio.create_task(self._worker_attempt(issue, attempt_num=None))

    async def _worker_attempt(self, issue: Issue, attempt_num: int | None) -> None:
        worker_log = get_logger().bind(issue_id=issue.id, identifier=issue.identifier)
        try:
            ws = await ensure_workspace(issue, self.config)
            self.state.running[issue.id].attempt.status = RunAttemptStatus.BUILDING_PROMPT
            self.state.running[issue.id].attempt.workspace_path = ws.path

            prompt = build_prompt(self.workflow.prompt_template, issue, attempt_num)
            self.state.running[issue.id].attempt.status = RunAttemptStatus.LAUNCHING_AGENT_PROCESS

            async def on_event(evt: dict) -> None:
                worker_log.info("symphony.agent.event", **evt)

            session = await self._runner.run(issue, ws, prompt, self.config, on_event)
            self.state.running[issue.id].session = session
            self.state.running[issue.id].attempt.status = RunAttemptStatus.SUCCEEDED
            worker_log.info("symphony.worker.succeeded")
        except AgentError as exc:
            worker_log.error("symphony.worker.failed", category=exc.category, error=str(exc))
            self._maybe_retry(issue, attempt_num, str(exc))
        except Exception as exc:
            worker_log.error("symphony.worker.error", error=str(exc))
            self._maybe_retry(issue, attempt_num, str(exc))
        finally:
            if issue.id in self.state.running:
                self.state.completed.add(issue.id)
                del self.state.running[issue.id]

    def _maybe_retry(self, issue: Issue, prev_attempt: int | None, error: str) -> None:
        next_attempt = (prev_attempt or 0) + 1
        delay_ms = _backoff_ms(next_attempt, self.config.max_retry_backoff_ms)
        log.info(
            "symphony.retry.scheduled",
            issue_id=issue.id,
            attempt=next_attempt,
            delay_ms=delay_ms,
        )
        entry = RetryEntry(
            issue_id=issue.id,
            identifier=issue.identifier,
            attempt=next_attempt,
            due_at_ms=int(time.monotonic() * 1000) + delay_ms,
            error=error,
        )
        self.state.retry_attempts[issue.id] = entry
        loop = asyncio.get_event_loop()
        loop.call_later(
            delay_ms / 1000.0,
            lambda: asyncio.create_task(self._on_retry_timer(issue, next_attempt)),
        )

    async def _on_retry_timer(self, issue: Issue, attempt_num: int) -> None:
        if issue.id in self.state.retry_attempts:
            del self.state.retry_attempts[issue.id]
        await self._worker_attempt(issue, attempt_num)

    def _release(self, issue_id: str) -> None:
        self.state.claimed.discard(issue_id)
        self.state.running.pop(issue_id, None)
        self.state.retry_attempts.pop(issue_id, None)
