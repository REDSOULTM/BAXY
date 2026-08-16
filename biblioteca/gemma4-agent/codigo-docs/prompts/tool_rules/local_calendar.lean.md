local_calendar(...): calendario offline ICS-compatible en state local. Actions: status, event_create, event_list, event_update, event_delete, ics_export, ics_import, list, delete.
ics_import: parsea VEVENT RFC 5545 con line folding; normaliza DTSTART/DTEND.
!= reminder (notif one-shot); != notes_tasks (sin time/date).
USAR: cualquier cosa con timestamp start/end que el user quiera en un calendario.
