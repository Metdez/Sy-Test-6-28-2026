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

workspace:
  root: ~/symphony_workspaces

agent:
  max_concurrent_agents: 3
  max_turns: 20
---

You are a coding agent working on issue {{issue.identifier}}: {{issue.title}}.

## Issue Description
{{issue.description}}

## Instructions
1. Read the issue carefully.
2. Make the required code changes.
3. Run tests to verify your changes.
4. Commit your work.
