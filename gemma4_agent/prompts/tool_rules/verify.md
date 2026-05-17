Verify rule: verify(...) checks observable structural facts after another action. Actions: app_opened, file_exists, window_exists, clipboard_contains.

NOT a domain tool — it confirms outcomes only. Use after a destructive or fire-and-forget action when the user needs an explicit "yes it actually happened" rather than just the dispatching tool's success flag.

Each per-tool verifier registered in verifiers.py also runs automatically post-call; verify(...) is the on-demand surface when the agent needs to assert a fact independently of the tool that produced it.
