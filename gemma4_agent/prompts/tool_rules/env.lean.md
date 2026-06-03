Env: env(...) lee/escribe variables de entorno Windows. Actions: get, set, delete, list. scope: process | user | machine.

- process: solo la sesión actual del agente.
- user/machine: scopes persistentes de Windows -> esos cambios registran checkpoints de rollback automáticamente.

Distinto de registry(...) (paths HKEY crudos) y device_settings(...) (WiFi/Bluetooth/displays). Usá env para PATH, PYTHONPATH, credenciales custom o feature flags expuestos vía env vars.
