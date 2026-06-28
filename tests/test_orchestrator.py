import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from symphony.config import build_config
from symphony.types import Issue, OrchestratorRuntimeState
from symphony.orchestrator import Orchestrator, _sort_issues, _backoff_ms

BASE_CFG = build_config({
    "tracker": {"kind": "linear", "api_key": "k", "project_slug": "p"},
    "agent": {"max_concurrent_agents": 2, "max_retry_backoff_ms": 300000},
    "polling": {"interval_ms": 100},
})

def make_issue(id: str, priority: int | None = None, created_at=None) -> Issue:
    from datetime import datetime, timezone
    return Issue(
        id=id, identifier=f"PRJ-{id}", title="T", state="Todo",
        priority=priority,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_sort_issues_by_priority_then_oldest():
    from datetime import datetime, timezone
    i1 = make_issue("1", priority=1, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    i2 = make_issue("2", priority=2, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    i3 = make_issue("3", priority=1, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    sorted_issues = _sort_issues([i1, i2, i3])
    # priority 1 before priority 2; among same priority, oldest first
    assert sorted_issues[0].id == "3"
    assert sorted_issues[1].id == "1"
    assert sorted_issues[2].id == "2"


def test_sort_issues_none_priority_last():
    i_none = make_issue("none", priority=None)
    i_p1 = make_issue("p1", priority=1)
    sorted_issues = _sort_issues([i_none, i_p1])
    assert sorted_issues[0].id == "p1"
    assert sorted_issues[1].id == "none"


def test_backoff_ms_exponential():
    assert _backoff_ms(attempt=1, max_ms=300000) < _backoff_ms(attempt=2, max_ms=300000)
    assert _backoff_ms(attempt=2, max_ms=300000) < _backoff_ms(attempt=3, max_ms=300000)


def test_backoff_ms_capped():
    huge = _backoff_ms(attempt=100, max_ms=300000)
    assert huge <= 300000


def test_orchestrator_init():
    wf = MagicMock()
    wf.config = BASE_CFG._data
    orch = Orchestrator(config=BASE_CFG, workflow=wf)
    assert orch.state.max_concurrent_agents == 2
    assert len(orch.state.running) == 0


@pytest.mark.asyncio
async def test_orchestrator_skips_claimed_issues():
    wf = MagicMock()
    wf.config = BASE_CFG._data
    orch = Orchestrator(config=BASE_CFG, workflow=wf)
    # Pre-claim issue-1
    orch.state.claimed.add("issue-1")

    dispatched = []
    async def fake_dispatch(issue):
        dispatched.append(issue.id)

    issues = [make_issue("issue-1"), make_issue("issue-2")]
    await orch._dispatch_eligible(issues, fake_dispatch)
    assert "issue-1" not in dispatched
    assert "issue-2" in dispatched
