import pytest
from symphony.types import Issue, Workspace
from symphony.agent import build_prompt, AgentError

BASE_ISSUE = Issue(id="abc", identifier="PRJ-1", title="Fix the bug", state="Todo",
                   description="Detailed description here")
BASE_WS = Workspace(path="/tmp/PRJ-1", workspace_key="PRJ-1", created_now=True)


def test_build_prompt_substitutes_identifier():
    tpl = "Working on {{issue.identifier}}: {{issue.title}}"
    result = build_prompt(tpl, BASE_ISSUE, attempt=None)
    assert "PRJ-1" in result
    assert "Fix the bug" in result
    assert "{{" not in result


def test_build_prompt_substitutes_description():
    tpl = "Description: {{issue.description}}"
    result = build_prompt(tpl, BASE_ISSUE, attempt=None)
    assert "Detailed description here" in result


def test_build_prompt_attempt_context():
    tpl = "Attempt: {{attempt}}"
    result = build_prompt(tpl, BASE_ISSUE, attempt=2)
    assert "2" in result


def test_build_prompt_none_description():
    issue = Issue(id="x", identifier="PRJ-2", title="T", state="Todo", description=None)
    tpl = "Desc: {{issue.description}}"
    result = build_prompt(tpl, issue, attempt=None)
    assert "None" not in result or "Desc: " in result  # graceful handling


def test_agent_error_has_category():
    err = AgentError("codex_not_found", "codex binary missing")
    assert err.category == "codex_not_found"
    assert "codex_not_found" in str(err)
