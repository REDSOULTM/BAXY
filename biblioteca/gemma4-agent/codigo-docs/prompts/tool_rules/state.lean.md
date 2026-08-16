state(...): tracks the agent's operational state. Actions: resources|cleanup_plan|cleanup|checkpoint|checkpoints|rollback_plan|rollback|note.
NOT a domain tool — bookkeeping (open resources, reversible checkpoints) so other tools clean up after themselves.
WARNING: rollback replays the reverse of a registered checkpoint — can undo file writes, env changes, container starts, etc. Call ONLY when the user explicitly asked to undo, or as part of a documented cleanup flow.
cleanup_plan returns what WOULD be cleaned (no-op); cleanup actually runs it.
