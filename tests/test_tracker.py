import pytest
import httpx
import respx
from symphony.config import build_config, ServiceConfig
from symphony.tracker.linear import (
    fetch_candidate_issues,
    fetch_issues_by_states,
    fetch_issue_states_by_ids,
    LinearError,
)

BASE_CONFIG = {
    "tracker": {"kind": "linear", "api_key": "test_key", "project_slug": "my-proj"},
}


def make_config(**overrides) -> ServiceConfig:
    raw = {**BASE_CONFIG}
    return build_config(raw)


ISSUE_FRAGMENT = {
    "id": "issue-abc",
    "identifier": "PRJ-1",
    "title": "Fix the bug",
    "description": "Details here",
    "priority": 1,
    "state": {"name": "Todo"},
    "branchName": "fix/bug",
    "url": "https://linear.app/my-proj/issue/PRJ-1",
    "labels": {"nodes": [{"name": "Bug"}, {"name": "P1"}]},
    "relations": {"nodes": []},
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedAt": "2026-01-02T00:00:00.000Z",
}

CANDIDATE_RESPONSE = {
    "data": {
        "issues": {
            "nodes": [ISSUE_FRAGMENT],
            "pageInfo": {"hasNextPage": False, "endCursor": "cursor1"},
        }
    }
}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_candidate_issues_returns_issues():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(200, json=CANDIDATE_RESPONSE)
    )
    cfg = make_config()
    issues = await fetch_candidate_issues(cfg)
    assert len(issues) == 1
    assert issues[0].identifier == "PRJ-1"
    assert issues[0].state == "Todo"


@pytest.mark.asyncio
@respx.mock
async def test_labels_normalized_to_lowercase():
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(200, json=CANDIDATE_RESPONSE)
    )
    cfg = make_config()
    issues = await fetch_candidate_issues(cfg)
    assert issues[0].labels == ["bug", "p1"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_raises_on_graphql_errors():
    error_response = {"errors": [{"message": "Unauthorized"}]}
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(200, json=error_response)
    )
    cfg = make_config()
    with pytest.raises(LinearError, match="linear_graphql_errors"):
        await fetch_candidate_issues(cfg)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_raises_on_http_error():
    respx.post("https://api.linear.app/graphql").mock(return_value=httpx.Response(401))
    cfg = make_config()
    with pytest.raises(LinearError, match="linear_api_status"):
        await fetch_candidate_issues(cfg)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_issue_states_by_ids_returns_map():
    state_response = {
        "data": {
            "issues": {
                "nodes": [{"id": "issue-abc", "state": {"name": "In Progress"}}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }
    respx.post("https://api.linear.app/graphql").mock(
        return_value=httpx.Response(200, json=state_response)
    )
    cfg = make_config()
    result = await fetch_issue_states_by_ids(["issue-abc"], cfg)
    assert result == {"issue-abc": "In Progress"}
