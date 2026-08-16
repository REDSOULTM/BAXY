---
name: notes-knowledge
description: Create, search, read, update, trash, and restore local notes while preserving exact note identity and versioning.
operations:
  - note.create
  - note.list
  - note.search
  - note.read
  - note.update
  - note.trash
  - note.restore
priority: 72
---
# Local notes

Use search/list only to discover candidates. Read the selected note before an
update and bind the update to its observed identity and version. If several
notes match, stop for disambiguation. `note.trash` is recoverable and is the only
deletion path; restore requires the exact trashed identity. Keep private-memory
requests out of this workflow because notes and memory have different authority.
