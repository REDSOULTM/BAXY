---
name: steam-library-install
description: Inspect Steam catalog, launch owned games, and prepare then confirm an installation safely.
operations:
  - game.catalog.list
  - game.launch
  - game.install.prepare
  - game.install.commit
  - game.install.status
  - game.install.cancel
priority: 85
---
# Steam library and installation

Use `game.catalog.list` for read-only ownership and installation questions.
Launch only an observed owned AppID with `game.launch` and verify the resulting
process identity. Installation is a two-step transaction:
`game.install.prepare` takes the literal AppID and returns a confirmation/job
identity; `game.install.commit` must depend on that step and ground its arguments
from the observed result after confirmation. Catalog presence is not proof of
ownership, installation, or launch.

Use `game.install.status` with the literal AppID to inspect queued, downloading,
installed, or absent state. Use `game.install.cancel` only when the user
explicitly asks to cancel that exact partial download; never substitute cancel
for uninstalling a completed game.
