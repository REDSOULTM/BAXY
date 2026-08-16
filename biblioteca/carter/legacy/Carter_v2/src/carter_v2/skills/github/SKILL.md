---
name: github
description: GitHub operations via gh CLI — PRs, issues, repos, CI runs, commits
triggers: [github, gh, PR, pull request, issue, repo, commit, branch, merge, CI, workflow, release]
requires: {bins: [gh]}
emoji: 🐙
source: builtin
---
# GitHub Skill

Use the `gh` CLI for all GitHub operations. Run commands via run_command.

## Setup check
`gh auth status`

## Pull Requests
```
gh pr list
gh pr view 55
gh pr create --title "feat: ..." --body "..."
gh pr merge 55 --squash
gh pr checks 55
```

## Issues
```
gh issue list --state open
gh issue create --title "Bug: ..." --body "..."
gh issue close 42
gh issue comment 42 --body "..."
```

## Repos
```
gh repo clone owner/repo
gh repo view
gh repo create my-repo --private
```

## CI / Workflow runs
```
gh run list --limit 10
gh run view <run-id> --log-failed
gh run rerun <run-id> --failed
```

## Tips
- Always add `--repo owner/repo` when not inside a git directory.
- Use `--json field1,field2 --jq '...'` for structured output.
- Use `gh api repos/owner/repo/...` for raw API access.
