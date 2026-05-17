Container rule: container(...) is a Docker / docker-compose wrapper. Actions: status, ps, ps_all, images, inspect, logs, start, stop, restart, exec, compose_up, compose_down, compose_ps.

Returns needs_dependency when docker is not on PATH — report that to the user instead of guessing.

start/stop/restart register rollback checkpoints with the reverse action so state(action='rollback') can undo them.

Distinct from terminal(...) which would run raw `docker` commands without checkpointing.
