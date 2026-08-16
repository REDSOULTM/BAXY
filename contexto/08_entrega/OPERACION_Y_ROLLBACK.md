# Operación y rollback

BAXY 1.0 se entrega como `Baxy.Setup.exe` NativeAOT autocontenido para Windows
x64. La instalación es por usuario, no requiere administrador y usa
`%LOCALAPPDATA%\Programs\BAXY`. Los datos viven aparte en
`%LOCALAPPDATA%\BAXY`.

## Artefacto reproducible final

El release final fue reconstruido desde el HEAD limpio
`455243c7c14fc915c9c70f7d356012dc5303e457` con .NET SDK 10.0.100:

- candidato 1.0.1: `Baxy.Setup.exe`, 87.040.000 bytes, SHA-256
  `68cfc30172b5b15e72e4085fcfb243107b54931d050f111d87cfb1991930cd83`;
- paquete 1.0.1: 83.121.455 bytes, SHA-256
  `fdded6df99c9353a1c752855d5279e0f88642fa940f911b1982951e15a866978`;
- shell 1.0.1: 67.161.077 bytes, SHA-256
  `2d9111876e4d8d0b61d7f0a59e755a71564383250738a20c592628fbfd010b00`;
- core 1.0.1: 7.570.432 bytes, SHA-256
  `97a3f426caa924584e63f48a88cae8dd4771e059572e1f6116d503b266aa7119`;
- predecesor 1.0.0: `Baxy.Setup.exe`, 87.040.000 bytes, SHA-256
  `22face7dc817f51fba6beebd3922d0b87e2cdd8b3a695cdf5ecfd8a8363553da`.

Las réplicas A/B del candidato coinciden byte a byte en los ocho archivos de
producto, dos de paquete y tres de Setup. Los tres Setup aprobaron
`--verify-embedded`; Authenticode informa `NotSigned`. Rutas, manifests,
checksums, árboles y límites están ligados en
`artifacts/setup/final_release_gate.json`.

## Artefacto del recorrido físico anterior

La evidencia de lifecycle está ligada al snapshot limpio
`d69a960226bb6e9a81de4bd39d9d708afc6f63a8`:

- predecesor 1.0.0: Setup de 87.016.960 bytes, SHA-256
  `c02defb9ad471cec4962c6a13f57a96edb27650e186b2cd765df8331fdf39a6b`;
- candidato 1.0.1: Setup de 87.016.960 bytes, SHA-256
  `fe2b16c14a7369713cb76333ce8a248b27ede216c357a45c55d253e5ee9b5be5`;
- paquete embebido 1.0.1: 83.098.211 bytes, SHA-256
  `7f74a66a8b6e40c4bf1c0dfc64a14d0300980db39a3b258a3cf448c409f05607`.

Las réplicas A/B del candidato son byte-idénticas. `SHA256SUMS` debe verificarse
antes de ejecutar el Setup. Los binarios permanecen `NotSigned`: el checksum
demuestra consistencia con la metadata conservada, no identidad de editor.

## Comandos soportados

- `Baxy.Setup.exe` instala o actualiza el payload embebido.
- El `Baxy.Setup.exe` de la raíz instalada con `--launch` abre la versión activa.
- El host instalado con `--rollback` intercambia `current` y
  `current.previous`, sólo si ambos payloads son íntegros y compatibles con el
  mismo `data_schema`.
- `--uninstall` desinstala conservando datos.
- `--uninstall --keep-data --quiet` hace lo mismo sin interacción.
- `--uninstall --purge-data --confirm-purge-data --quiet` es la única forma de
  eliminar también `%LOCALAPPDATA%\BAXY`.

No existe un worker, servicio, tarea programada, Run/RunOnce ni journal propio
de desinstalación. El Setup verifica su identidad, punteros, integración,
shortcut y registro; mueve la raíz instalada a un sibling único y usa el
`cmd.exe` de System32 para retirarla después de terminar. Keep-data no inspecciona
la hoja del directorio de datos.

## Estado y recuperación

Las versiones publicadas son inmutables. `current` identifica la versión activa
y `current.previous` la única opción productiva de rollback. Install, update y
rollback usan transacciones durables y reconciliación de host estable, acceso
directo y registro de desinstalación. Corrupción, versión no creciente, cambio
de `data_schema` o estado exterior ajeno fallan cerrados.

No se deben editar punteros, copiar archivos sobre una versión publicada ni
borrar manualmente `%LOCALAPPDATA%\Programs\BAXY`. Ante un fallo, conservar el
árbol y capturar `current`, `current.previous`, `installation.v1.json` y
`windows-integration.v1.json` antes de reintentar con un Setup cuyo checksum se
haya verificado.

## Evidencia física y límite actual

El recorrido versionado aprobó instalación 1.0.0, actualización a 1.0.1,
rollback a 1.0.0 y desinstalación keep-data. El acceso directo, registro, raíz
instalada, tombstone y procesos desaparecieron; un canary propio de datos
permaneció byte-idéntico. Véase
`artifacts/setup/gate14_lifecycle_gate.json`.

Esto todavía no promueve Gate 14: se ejecutó en el perfil actual, que ya tenía
tres entradas BAXY. Primer inicio instalado y purge-data deben probarse en una
cuenta o VM desechable realmente limpia. No se autoriza usar los datos actuales
para completar esa prueba destructiva.

Los dos comandos finales de una sola ejecución —`app.open` en sesión quieta y
lifecycle/purge en perfil desechable— están en
`contexto/06_pruebas_y_mediciones/GATES_APLAZADOS_EQUIPO_LIMPIO.md` y apuntan
al release final registrado arriba.
