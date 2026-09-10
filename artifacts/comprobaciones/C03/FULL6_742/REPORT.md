# Full6 — C03, ejecución 742

`powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/test_source_quality.ps1 -Mode Full`

Terminó con exit **1** en **1519,468 s**. Los **1233 archivos congelados permanecieron idénticos** durante toda la corrida.

- .NET: 4574 pass, 0 fail, 1 skip agregado. El log también conserva 16 mensajes explícitos de omisiones opt-in; no son passes.
- Python: 11398 pass, 1 fail, 3 skips ambientales y 466 subtests pass; 736,77 s.
- Único fallo: `tests/test_price_v8_veto_damage_by_cause.py::test_published_split_and_ceiling_are_the_numbers_r144_reported`. La allowlist de la versión actual de `__main__.py` no reflejaba la reparación 740. No falló la evidencia V8 histórica.
- Las pruebas originales de sidecar y empaquetado pasaron; sus límites de 3 y 45 segundos siguieron intactos.

`RESULT.json` conserva el resultado original y el hash del log privado sin normalizar. `ADJUDICATION.json` separa ese hash del log público en LF. No se adoptó fuente con esta corrida roja. La reparación y la validación posterior están en `../PUBLICATION744/REPORT.md`.
