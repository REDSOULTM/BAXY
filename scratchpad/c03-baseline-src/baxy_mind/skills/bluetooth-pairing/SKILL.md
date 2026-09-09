---
name: bluetooth-pairing
description: Enumerate Bluetooth devices and pair one stable device identity with OS verification.
operations:
  - bluetooth.device.list
  - bluetooth.device.pair
priority: 75
---
# Bluetooth pairing

Always enumerate with `bluetooth.device.list` before pairing. Select exactly one
observed stable device ID; never pass a friendly name as an invented ID. Pairing
depends on that enumeration and may require a system prompt or confirmation.
Success means Windows reports the same device identity as paired after the job;
opening Bluetooth settings is not sufficient evidence.
