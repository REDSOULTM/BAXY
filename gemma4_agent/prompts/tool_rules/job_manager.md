Job-manager rule: job_manager(...) tracks long-running detached subprocesses. Actions: status, start, list, log, status_of, cancel.

start spawns a detached process with stdout/stderr redirected to a log file and registers it in state with its PID. cancel uses taskkill /T to terminate the process tree.

Distinct from terminal(action='run') (synchronous, blocks the turn) and from container(...) (Docker only). Use job_manager for builds, long downloads, training jobs, etc.

Always cite the job id returned by start so subsequent turns can reference it.
