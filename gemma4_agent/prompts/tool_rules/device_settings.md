Device-settings rule: device_settings(...) manages WiFi, Bluetooth, displays and power plans. WiFi actions: wifi_status, wifi_list, wifi_scan, wifi_connect, wifi_disconnect, wifi_add_profile, wifi_delete_profile, plus bluetooth_* and display/power equivalents (see schema).

wifi_connect auto-creates a WPA2-Personal profile when a password is passed. Profile changes register checkpoints so state(action='rollback') can undo them.

Distinct from network(...) (diagnostics: ping, dns, http) and from system(...) (read-only OS metrics + power actions).
