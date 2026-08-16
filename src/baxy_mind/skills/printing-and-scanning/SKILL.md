---
name: printing-and-scanning
description: Enumerate peripherals before an exact print or scan job and verify job or output identity.
operations:
  - peripheral.list
  - peripheral.print
  - peripheral.scan
priority: 75
---
# Printing and scanning

Start with `peripheral.list` and select one observed device ID. Printing requires
an exact local document identity and explicit printer; do not choose defaults
silently. Verify the spooler job and terminal state, not merely queue
submission. Scanning requires an observed device and succeeds only when the
private captured artifact can be reopened and hashed. The scan
provider selects its private output path; the planner supplies only the
observed scanner ID. Hardware or paper absence is an environment blocker,
never a simulated success.
