Terminal rule: terminal(action='run') executes a shell command with command, args, cwd, timeout_sec, shell. Lower-level than developer(...) (git/build-aware).

HARD GATE: any terminal.run requires confirmed=true. shell defaults to false — pass shell=true ONLY when shell expansion is needed.

NEVER bypass purchase-guard or safety via terminal (e.g. don't shell out an installer that requires payment). Destructive commands (rm -rf, format, reg delete) -> confirm even without safety_enabled.

Prefer developer(action='git_*') for git workflows over terminal — developer is aware of project root and stack.
