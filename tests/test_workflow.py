import textwrap
from pathlib import Path
import pytest
from symphony.workflow import load_workflow
from symphony.types import WorkflowDefinition

SAMPLE_WORKFLOW = textwrap.dedent("""\
    ---
    tracker:
      kind: linear
      api_key: $LINEAR_API_KEY
      project_slug: my-project
      active_states:
        - "Todo"
        - "In Progress"
    polling:
      interval_ms: 30000
    ---

    You are working on issue {{issue.identifier}}: {{issue.title}}.

    ## Description
    {{issue.description}}
    """)


@pytest.fixture
def workflow_file(tmp_path: Path) -> Path:
    f = tmp_path / "WORKFLOW.md"
    f.write_text(SAMPLE_WORKFLOW)
    return f


def test_load_workflow_returns_definition(workflow_file):
    wf = load_workflow(str(workflow_file))
    assert isinstance(wf, WorkflowDefinition)


def test_load_workflow_parses_front_matter(workflow_file):
    wf = load_workflow(str(workflow_file))
    assert wf.config["tracker"]["kind"] == "linear"
    assert wf.config["tracker"]["project_slug"] == "my-project"
    assert wf.config["polling"]["interval_ms"] == 30000


def test_load_workflow_extracts_prompt_body(workflow_file):
    wf = load_workflow(str(workflow_file))
    assert "{{issue.identifier}}" in wf.prompt_template
    assert "{{issue.title}}" in wf.prompt_template
    assert "---" not in wf.prompt_template.strip()


def test_load_workflow_prompt_is_trimmed(workflow_file):
    wf = load_workflow(str(workflow_file))
    assert not wf.prompt_template.startswith("\n")


def test_load_workflow_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_workflow(str(tmp_path / "missing.md"))


def test_load_workflow_no_front_matter_raises(tmp_path):
    f = tmp_path / "bad.md"
    f.write_text("Just a prompt with no front matter.\n")
    with pytest.raises(ValueError, match="front matter"):
        load_workflow(str(f))
