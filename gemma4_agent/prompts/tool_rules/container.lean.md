Container: container(...) = wrapper Docker / docker-compose. Actions: status, ps, ps_all, images, inspect, logs, start, stop, restart, exec, compose_up, compose_down, compose_ps.

- Si docker no está en PATH -> devuelve needs_dependency: reportalo al usuario, NO adivines.
- start/stop/restart registran checkpoints con la acción inversa -> state(action='rollback') los deshace.

Distinto de terminal(...) que correría comandos `docker` crudos SIN checkpointing.
