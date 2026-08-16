Local-calendar rule: local_calendar(...) is an offline ICS-compatible calendar in local state. Actions: status, event_create, event_list, event_update, event_delete, ics_export, ics_import, list, delete.

ics_import parses RFC 5545 VEVENT blocks with line folding and normalizes DTSTART/DTEND.

Distinct from reminder(...) (one-shot notifications) and from notes_tasks(...) (no time/date). Use local_calendar for anything with a start/end timestamp the user wants to keep on a calendar.
