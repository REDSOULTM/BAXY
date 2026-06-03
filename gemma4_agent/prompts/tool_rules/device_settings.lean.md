Device-settings: device_settings(...) = WiFi, Bluetooth, displays, planes de energía. WiFi actions: wifi_status, wifi_list, wifi_scan, wifi_connect, wifi_disconnect, wifi_add_profile, wifi_delete_profile; + bluetooth_* y equivalentes display/power (ver schema).

- wifi_connect: auto-crea perfil WPA2-Personal si se pasa password.
- Cambios de perfil registran checkpoints -> state(action='rollback') los deshace.

Distinto de network(...) (diag: ping/dns/http) y system(...) (métricas OS read-only + acciones de energía).
