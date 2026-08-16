# Carter OS AI — Project Instructions for Gemini CLI

You are working on Carter v2, a local Windows AI assistant written in Python.

Primary goals:
- Stabilize the project without breaking existing behavior.
- Prefer small, verifiable changes over large rewrites.
- Do not invent architecture. Read the code first.
- Before editing files, explain the plan.
- After editing, run the relevant tests or verification commands.
- If tests fail, stop and report the exact failure.
- Keep configuration centralized where reasonable, preferably through `.env`, config files, or a single settings module.
- Avoid hardcoded paths, model names, flags, ports, or credentials.
- Preserve local-first/privacy-first behavior.
- Do not add cloud dependencies unless explicitly requested.
- Do not remove existing safety gates without explaining the risk.

Workflow:
1. Inspect the repository structure.
2. Read README, pyproject, config files, tests, and main entrypoints.
3. Identify real problems only.
4. Propose a phased plan.
5. Wait for approval before applying large changes.
6. Make small commits or change groups.
7. Verify after each phase.

Important:
- This project is on Windows.
- Use PowerShell-compatible commands.
- Python version target is 3.10.