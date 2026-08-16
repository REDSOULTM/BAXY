State rule: state(...) tracks the agent's operational state. Actions: resources, cleanup_plan, cleanup, checkpoint, checkpoints, rollback_plan, rollback, note.

NOT a domain tool — it manages bookkeeping (open resources, reversible checkpoints) so other tools can clean up after themselves.

WARNING: state(action='rollback') replays the reverse of a registered checkpoint — it can undo file writes, env changes, container starts, etc. Only call it when the user explicitly asked to undo, or as part of a documented cleanup flow.

cleanup_plan returns what WOULD be cleaned without doing it; cleanup actually runs it.
