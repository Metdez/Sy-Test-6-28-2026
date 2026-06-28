"""Domain model — all types match PRD §4.1 field names exactly."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunAttemptStatus(StrEnum):
    PREPARING_WORKSPACE = "PreparingWorkspace"
    BUILDING_PROMPT = "BuildingPrompt"
    LAUNCHING_AGENT_PROCESS = "LaunchingAgentProcess"
    INITIALIZING_SESSION = "InitializingSession"
    STREAMING_TURN = "StreamingTurn"
    FINISHING = "Finishing"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    TIMED_OUT = "TimedOut"
    STALLED = "Stalled"
    CANCELED_BY_RECONCILIATION = "CanceledByReconciliation"


class OrchestrationState(StrEnum):
    UNCLAIMED = "Unclaimed"
    CLAIMED = "Claimed"
    RUNNING = "Running"
    RETRY_QUEUED = "RetryQueued"
    RELEASED = "Released"


class BlockerRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    identifier: str | None = None
    state: str | None = None


class Issue(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    identifier: str
    title: str
    description: str | None = None
    priority: int | None = None
    state: str
    branch_name: str | None = None
    url: str | None = None
    labels: list[str] = Field(default_factory=list)
    blocked_by: list[BlockerRef] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    config: dict[str, Any]
    prompt_template: str


class Workspace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    path: str
    workspace_key: str
    created_now: bool = False


class RunAttempt(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    issue_id: str
    issue_identifier: str
    attempt: int | None = None
    workspace_path: str
    started_at: datetime
    status: RunAttemptStatus
    error: str | None = None


class LiveSession(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str
    thread_id: str
    turn_id: str
    codex_app_server_pid: str | None = None
    last_codex_event: str | None = None
    last_codex_timestamp: datetime | None = None
    last_codex_message: str | None = None
    codex_input_tokens: int = 0
    codex_output_tokens: int = 0
    codex_total_tokens: int = 0
    last_reported_input_tokens: int = 0
    last_reported_output_tokens: int = 0
    last_reported_total_tokens: int = 0
    turn_count: int = 0


class RetryEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    issue_id: str
    identifier: str
    attempt: int
    due_at_ms: int
    error: str | None = None


class RunningEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    issue_id: str
    issue_identifier: str
    attempt: RunAttempt
    session: LiveSession | None = None


class OrchestratorRuntimeState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    poll_interval_ms: int
    max_concurrent_agents: int
    running: dict[str, RunningEntry] = Field(default_factory=dict)
    claimed: set[str] = Field(default_factory=set)
    retry_attempts: dict[str, RetryEntry] = Field(default_factory=dict)
    completed: set[str] = Field(default_factory=set)
