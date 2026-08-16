---
name: filesystem-safe-changes
description: Inspect and change files inside BAXY's sandbox with hashes, backups, reversible trash, and explicit dependencies.
operations:
  - filesystem.list
  - filesystem.search
  - filesystem.read.text
  - filesystem.hash
  - filesystem.create.directory
  - filesystem.copy
  - filesystem.move
  - filesystem.write.text
  - filesystem.trash.prepare
  - filesystem.trash.commit
  - filesystem.trash.restore
  - backup.create
  - backup.verify
  - backup.restore
priority: 88
---
# Safe filesystem changes

Observe before mutating. Use `filesystem.hash` before replacing content and pass
the observed SHA-256 as the compare-and-swap precondition. Create and verify a
backup before a multi-step rewrite when the objective requires preservation.
Deletion is always `filesystem.trash.prepare` followed by a dependent
`filesystem.trash.commit`; never infer a permanent delete. Use result references
only from verified predecessor steps and keep every path relative to the sandbox.
