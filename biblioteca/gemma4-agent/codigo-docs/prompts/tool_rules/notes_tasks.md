Notes/tasks rule: notes_tasks(...) is a local notes + tasks store. Note actions: note_create, note_list, note_search, note_update, note_delete. Task actions: task_create, task_list, task_search, task_complete, task_update, task_delete.

Distinct from memory(...) (long-term key-value the user explicitly asks to remember), from local_calendar(...) (events with timestamps), and from reminder(...) (one-shot notifications).

Use notes_tasks when the user wants something written down for later reference, or wants to track an open to-do.
