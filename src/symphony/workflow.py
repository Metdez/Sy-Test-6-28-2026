"""Workflow loader — parses WORKFLOW.md YAML front matter + prompt body (PRD §3.1.1, §5)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from symphony.types import WorkflowDefinition

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def load_workflow(path: str) -> WorkflowDefinition:
    content = Path(path).read_text(encoding="utf-8")  # raises FileNotFoundError if missing

    match = _FRONT_MATTER_RE.match(content)
    if not match:
        raise ValueError(f"WORKFLOW.md at '{path}' has no YAML front matter (expected --- ... ---)")

    raw_yaml = match.group(1)
    config: dict[str, Any] = yaml.safe_load(raw_yaml) or {}

    # Everything after the closing --- is the prompt body
    prompt_template = content[match.end():].strip()

    return WorkflowDefinition(config=config, prompt_template=prompt_template)
