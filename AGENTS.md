# AGENTS.md

## 🛡️ SpecGuard Enforced

This repository uses **SpecGuard** to ensure code quality and security.
As an AI agent, you **MUST** follow this workflow:

1.  **Edit**: Make your code changes.
2.  **Validate**: Run the validation script to check for issues.
    ```bash
    npm run validate:staged
    ```
3.  **Repair**: If validation fails, fix the errors and re-run.
4.  **Report**: Include the validation summary in your final response.

**Available Scripts:**
| Command | What it does |
|---|---|
| `npm run validate` | Validate all working files |
| `npm run validate:staged` | Validate only staged (pre-commit) files |
| `npm run validate:ci` | Validate with machine-readable JSON output |
| `npm run guard` | Run an AI agent with SpecGuard loop control (auto-repair) |

**Artifacts Location:**
- Spec: `.ai/specguard/spec.yaml`
- Reports: `.ai/specguard/reports/`

**Safety Rules:**
- 🚫 NO secrets in code.
- 🚫 NO shell execution in tool steps (unless explicitly allowed).
- ✅ ALWAYS verify your changes.
