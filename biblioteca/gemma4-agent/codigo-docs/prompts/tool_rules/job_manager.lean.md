Job-manager: job_manager(...) trackea subprocesos detached largos. Actions: status, start, list, log, status_of, cancel.

- start: spawnea proceso detached con stdout/stderr a un log y lo registra en state con su PID.
- cancel: taskkill /T (mata el árbol de procesos).

Distinto de terminal(action='run') (síncrono, bloquea el turno) y container(...) (solo Docker). Usá job_manager para builds, descargas largas, training jobs, etc.

Citá SIEMPRE el job id que devuelve start para que turnos siguientes lo referencien.
