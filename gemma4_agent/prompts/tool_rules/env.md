Environment-variable rule: env(...) reads and writes Windows environment variables. Actions: get, set, delete, list. scope is one of process, user, machine.

process affects only the current agent session; user and machine are persistent Windows scopes — those changes register rollback checkpoints automatically.

Distinct from registry(...) (raw HKEY paths) and from device_settings(...) (WiFi, Bluetooth, displays). Reach for env when the user wants PATH, PYTHONPATH, custom credentials, or feature flags exposed via env vars.
