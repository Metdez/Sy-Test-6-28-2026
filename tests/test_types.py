from datetime import datetime, timezone
from symphony.types import (
    Issue, BlockerRef, WorkflowDefinition, Workspace,
    RunAttempt, RunAttemptStatus, LiveSession, RetryEntry,
    RunningEntry, OrchestratorRuntimeState, OrchestrationState,
)


def test_issue_minimal():
    issue = Issue(id="abc", identifier="PRJ-1", title="Fix bug", state="Todo")
    assert issue.labels == []
    assert issue.blocked_by == []
    assert issue.description is None


def test_issue_labels_lowercase():
    issue = Issue(id="abc", identifier="PRJ-1", title="T", state="Todo", labels=["Bug", "P1"])
    assert issue.labels == ["Bug", "P1"]  # normalization happens in tracker, not model


def test_run_attempt_status_enum_round_trip():
    status = RunAttemptStatus.SUCCEEDED
    assert RunAttemptStatus(status.value) == RunAttemptStatus.SUCCEEDED
    assert status.value == "Succeeded"


def test_live_session_token_defaults_zero():
    session = LiveSession(session_id="t1-t1", thread_id="t1", turn_id="t1")
    assert session.codex_input_tokens == 0
    assert session.codex_output_tokens == 0
    assert session.turn_count == 0


def test_orchestrator_state_sets():
    state = OrchestratorRuntimeState(poll_interval_ms=30000, max_concurrent_agents=10)
    assert isinstance(state.claimed, set)
    assert isinstance(state.completed, set)
    state.claimed.add("issue-1")
    assert "issue-1" in state.claimed


def test_orchestration_state_enum():
    assert OrchestrationState.UNCLAIMED.value == "Unclaimed"
    assert OrchestrationState.RETRY_QUEUED.value == "RetryQueued"
