"""Linear GraphQL adapter — fetch, normalize, error-map (PRD §3.1.3, §11)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from symphony.config import ServiceConfig
from symphony.types import BlockerRef, Issue

_PAGE_SIZE = 50
_NETWORK_TIMEOUT = 30.0

_CANDIDATE_QUERY = """
query CandidateIssues($projectSlug: String!, $states: [String!]!, $first: Int!, $after: String) {
  issues(
    filter: {
      project: { slugId: { eq: $projectSlug } }
      state: { name: { in: $states } }
    }
    first: $first
    after: $after
    orderBy: createdAt
  ) {
    nodes {
      id identifier title description priority branchName url
      state { name }
      labels { nodes { name } }
      relations(filter: { type: { eq: "blocks" } }) {
        nodes { relatedIssue { id identifier state { name } } }
      }
      createdAt updatedAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_STATES_QUERY = """
query IssuesByStates($states: [String!]!, $first: Int!, $after: String) {
  issues(filter: { state: { name: { in: $states } } } first: $first after: $after) {
    nodes { id identifier title description priority branchName url
      state { name }
      labels { nodes { name } }
      relations(filter: { type: { eq: "blocks" } }) {
        nodes { relatedIssue { id identifier state { name } } }
      }
      createdAt updatedAt }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_STATES_BY_IDS_QUERY = """
query IssueStatesByIds($ids: [ID!]!) {
  issues(filter: { id: { in: $ids } } first: 250) {
    nodes { id state { name } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class LinearError(Exception):
    def __init__(self, category: str, message: str) -> None:
        self.category = category
        super().__init__(f"{category}: {message}")


def _normalize_issue(node: dict[str, Any]) -> Issue:
    labels = [n["name"].strip().lower() for n in node.get("labels", {}).get("nodes", [])]
    blocked_by = [
        BlockerRef(
            id=rel["relatedIssue"].get("id"),
            identifier=rel["relatedIssue"].get("identifier"),
            state=rel["relatedIssue"].get("state", {}).get("name"),
        )
        for rel in node.get("relations", {}).get("nodes", [])
        if rel.get("relatedIssue")
    ]
    priority = node.get("priority")
    if not isinstance(priority, int):
        priority = None

    def parse_dt(v: str | None) -> datetime | None:
        return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None

    return Issue(
        id=node["id"],
        identifier=node["identifier"],
        title=node["title"],
        description=node.get("description"),
        priority=priority,
        state=node["state"]["name"],
        branch_name=node.get("branchName"),
        url=node.get("url"),
        labels=labels,
        blocked_by=blocked_by,
        created_at=parse_dt(node.get("createdAt")),
        updated_at=parse_dt(node.get("updatedAt")),
    )


async def _gql(
    query: str, variables: dict[str, Any], config: ServiceConfig
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_NETWORK_TIMEOUT) as client:
        try:
            resp = await client.post(
                config.tracker_endpoint,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": config.tracker_api_key,
                    "Content-Type": "application/json",
                },
            )
        except httpx.RequestError as e:
            raise LinearError("linear_api_request", str(e)) from e

        if resp.status_code != 200:
            raise LinearError("linear_api_status", f"HTTP {resp.status_code}")

        body = resp.json()
        if "errors" in body:
            raise LinearError("linear_graphql_errors", str(body["errors"]))

        return body.get("data", {})


async def _paginate_issues(
    query: str, variables: dict[str, Any], config: ServiceConfig
) -> list[Issue]:
    issues: list[Issue] = []
    after: str | None = None

    while True:
        data = await _gql(query, {**variables, "first": _PAGE_SIZE, "after": after}, config)
        conn = data.get("issues", {})
        for node in conn.get("nodes", []):
            issues.append(_normalize_issue(node))
        page_info = conn.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            raise LinearError("linear_missing_end_cursor", "hasNextPage=true but no endCursor")

    return issues


async def fetch_candidate_issues(config: ServiceConfig) -> list[Issue]:
    return await _paginate_issues(
        _CANDIDATE_QUERY,
        {"projectSlug": config.tracker_project_slug, "states": config.tracker_active_states},
        config,
    )


async def fetch_issues_by_states(state_names: list[str], config: ServiceConfig) -> list[Issue]:
    return await _paginate_issues(_STATES_QUERY, {"states": state_names}, config)


async def fetch_issue_states_by_ids(
    issue_ids: list[str], config: ServiceConfig
) -> dict[str, str]:
    if not issue_ids:
        return {}
    data = await _gql(_STATES_BY_IDS_QUERY, {"ids": issue_ids}, config)
    return {
        node["id"]: node["state"]["name"]
        for node in data.get("issues", {}).get("nodes", [])
    }
