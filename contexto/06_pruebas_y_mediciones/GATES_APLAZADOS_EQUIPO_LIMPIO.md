# Gates aplazados — equipo/perfil limpio

Estado: **pendiente-por-entorno (esperando equipo limpio del usuario)**.
Fecha de preparación: 2026-07-15.

Estos dos recorridos están preparados pero no se ejecutan en el perfil actual.
El Notepad preexistente PID 5472 y las tres entradas BAXY preexistentes quedan
fuera de alcance. No se debe cerrar ese proceso, inspeccionar esos datos ni
adaptar los scripts para eludir la precondición.

Los paths de abajo corresponden al release final de `455243c` y están ligados
por hashes en `artifacts/setup/final_release_gate.json`. No sustituirlos por un
build sucio o por el artefacto histórico del recorrido same-host.

## Gate 13 — `app.open`

Precondiciones automáticas:

- cero procesos Notepad, Baxy, baxy-core o Baxy.Setup;
- build final existente bajo `artifacts/product/build`;
- hoja `%LOCALAPPDATA%\BAXY\app-open-gate` inexistente.

Una sola ejecución:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test_app_open.ps1 -BuildRoot ".\artifacts\product\build\final-candidate-a-product" -EvidencePath .\artifacts\product\app_open_gate.json -AllowCloseVerifiedNotepadInQuiescentSession
```

El script exige un Notepad nuevo, verifica PID, creación, ejecutable/paquete,
HWND visible y foreground, replay con la misma invocación y supervivencia al
cierre del Job del core. Solo cierra normalmente el Notepad cuya identidad y
ventana creó y verificó. Elimina únicamente su hoja `app-open-gate`, publica la
evidencia JSON y exige cero procesos propios residuales.

## Gate 14 — instalación limpia y purge

Debe ejecutarse en una cuenta o VM desechable que conserve el repositorio y el
release final, pero no tenga raíz de instalación, datos, acceso directo,
registro, tombstones ni procesos BAXY.

Una sola ejecución:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\test_gate14_clean_environment.ps1 -PredecessorSetup ".\artifacts\setup\build\final-predecessor-setup\Baxy.Setup.exe" -CandidateSetup ".\artifacts\setup\build\final-candidate-a-setup\Baxy.Setup.exe" -EvidencePath .\artifacts\setup\gate14_clean_environment_gate.json -ConfirmDisposableProfile
```

El script verifica los `SHA256SUMS` y manifests adyacentes y luego ejecuta:

1. instalación 1.0.0;
2. primer inicio instalado y cierre normal del proceso propio;
3. creación de un canary propio;
4. update a 1.0.1 (`current.previous=1.0.0`);
5. rollback a 1.0.0 (`current.previous=1.0.1`);
6. uninstall keep-data y verificación byte a byte del canary;
7. reinstalación 1.0.1;
8. uninstall purge con el token exacto de confirmación;
9. ausencia final de instalación, datos, integración, tombstones y procesos.

El switch `-ConfirmDisposableProfile` es intencional: autoriza la purga solo en
ese perfil desechable. Si cualquier precondición no es prístina, el script falla
antes de instalar o borrar. En un fallo intermedio no inventa recuperación ni
continúa con una purga: conserva la evidencia para diagnóstico.

## Criterio de promoción

`app.open` solo promueve su parte física cuando `app_open_gate.json` diga
`status=passed`. Gate 14 solo completa su tramo pendiente cuando
`gate14_clean_environment_gate.json` diga `status=passed`. Hasta entonces no se
infieren esos claims desde el recorrido same-host ni desde tests unitarios.
