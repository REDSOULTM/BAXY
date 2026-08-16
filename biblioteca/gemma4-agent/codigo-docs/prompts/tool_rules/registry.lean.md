Registry: registry(...) = superficie segura del registro Windows. Actions: query, export, import, add, delete, backup.

DESTRUCTIVO (add/delete): exportan backup .reg ANTES + crean checkpoints rollback. Aun así NO los invoques salvo pedido claro — editar el registro puede brickear instalaciones.

Distinto de env(...) (solo env vars) y device_settings(...) (WiFi/BT/display). Usá registry SOLO si el usuario referencia explícito paths HKLM/HKCU o un tweak conocido a nivel registro.
