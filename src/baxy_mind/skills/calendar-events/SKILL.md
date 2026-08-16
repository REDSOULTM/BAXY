---
name: calendar-events
description: List calendar state or create one timezone-explicit event and read it back.
operations:
  - calendar.event.list
  - calendar.event.create
  - system.time
priority: 75
---
# Calendar events

Use `calendar.event.list` for inspection. Creation requires a literal title and
an unambiguous start/end that can be normalized to UTC; never guess a date,
year, duration, attendee or timezone. `system.time` may establish the current
clock when relative time is otherwise fully specified. Success requires the
authenticated Outlook provider to read back the event identity and canonical
UTC timestamps.
