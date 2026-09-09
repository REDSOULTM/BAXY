---
name: steam-purchase-guard
description: Prepare a specific Steam purchase, show exact price and commit only after current confirmation.
operations:
  - game.purchase.prepare
  - game.purchase.commit
priority: 100
---
# Steam purchase guard

A purchase always uses both primitives. `game.purchase.prepare` receives the
literal AppID and returns the exact selection, price, currency and
`confirmationId` without moving money. `game.purchase.commit` depends directly
on that verified step, uses `after_dependencies`, and is blocked by the core
until the current prepared purchase is explicitly confirmed. Never invent a
price or confirmation ID. An ambiguous result may have moved money: stop and do
not retry automatically.
