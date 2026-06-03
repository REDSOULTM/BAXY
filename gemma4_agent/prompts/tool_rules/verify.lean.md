verify(...): checks observable structural facts AFTER another action. Actions: app_opened|file_exists|window_exists|clipboard_contains.
NOT a domain tool — confirms outcomes only. Use after a destructive or fire-and-forget action when the user needs explicit "yes it actually happened" rather than just the dispatching tool's success flag.
Each per-tool verifier in verifiers.py also auto-runs post-call; verify(...) is the on-demand surface to assert a fact independently of the tool that produced it.
