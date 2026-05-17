Registry rule: registry(...) is the safe Windows registry surface. Actions: query, export, import, add, delete, backup.

DESTRUCTIVE: add / delete export a .reg backup first and create rollback checkpoints. Still, do not invoke these unless the user clearly asked — registry edits can brick installations.

Distinct from env(...) (environment variables only, friendlier scope model) and from device_settings(...) (high-level WiFi / Bluetooth / display). Reach for registry only when the user explicitly references HKLM/HKCU paths or a known registry-level tweak.
