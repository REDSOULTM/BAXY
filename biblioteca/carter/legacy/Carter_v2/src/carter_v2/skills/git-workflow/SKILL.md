---
name: git-workflow
description: Standard git workflow — status, commit, push, pull, branch, merge, stash
triggers: [git, commit, push, pull, branch, merge, stash, rebase, status, diff, log, clone, checkout]
requires: {bins: [git]}
emoji: 🌿
source: builtin
---
# Git Workflow Skill

Use git via git_run action (preferred) or run_command for git operations.

## Daily workflow
```
git status
git diff
git add .
git commit -m "feat: description"
git push
git pull
```

## Branches
```
git branch                   # list branches
git checkout -b feature/name # create and switch
git checkout main            # switch branch
git merge feature/name       # merge into current
git branch -d feature/name   # delete branch
```

## Stash
```
git stash                    # save changes temporarily
git stash pop                # restore last stash
git stash list               # see all stashes
```

## History
```
git log --oneline -10        # last 10 commits
git log --graph --oneline    # visual tree
git diff HEAD~1              # diff with previous commit
git show <commit>            # show commit details
```

## Undo
```
git restore <file>           # discard unstaged changes
git reset HEAD <file>        # unstage file
git revert <commit>          # create undo commit (safe)
```

## Remote
```
git remote -v                # show remotes
git fetch origin             # fetch without merge
git push -u origin branch    # push and track
```

## Tips
- Prefer git_run action for safe git operations (Carter validates subcommands)
- Use run_command for git commands not covered by git_run
- Always check git status before committing
