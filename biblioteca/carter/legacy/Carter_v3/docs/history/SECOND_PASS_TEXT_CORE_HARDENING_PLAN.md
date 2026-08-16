# SECOND PASS TEXT CORE HARDENING PLAN

## Problemas encontrados

1. **Bug real en resolver/verificacion de procesos (`app_open`)**
   - En `src/carter_v3/tools/dispatch_app.py`, `_matching_process_names` tiene una indentacion incorrecta:
     - `bare = name.lower().replace(".exe", "")` queda dentro del `if not name: continue`, por lo que no se ejecuta en el camino normal.
   - Impacto: baseline de procesos para verificacion causal puede quedar incompleto o vacio.

2. **Estado terminal de trazabilidad para `partial` no es explicito**
   - En `agent.py`, `MissionStatus.PARTIAL` se proyecta como `COMPLETED` en `turn_state_sequence`.
   - Impacto: reduce honestidad operacional; “parcial” no debe parecer “completado”.

3. **Cobertura insuficiente de edge-cases contra fake success / estados terminales**
   - Faltan pruebas explicitas para:
     - `terminal_run_command` con salida incompleta/no verificable;
     - `filesystem_write_text` verificado vs no verificable;
     - `verifier skipped/failed/unverifiable/confirmed sin evidencia util`;
     - mapping de `MissionStatus` a estado terminal en `turn_state_sequence`.

---

## Cambios maximos permitidos (3)

### Cambio 1 (codigo): fix bug `_matching_process_names`

- **Archivo:** `src/carter_v3/tools/dispatch_app.py`
- **Accion:** corregir indentacion/logica para calcular `bare` y matching exact/partial.
- **Riesgo:** bajo.
- **Rollback:** revertir solo este archivo.

### Cambio 2 (codigo): estado terminal explicito para parcial

- **Archivos:** `src/carter_v3/trace.py`, `src/carter_v3/agent.py`
- **Accion:** agregar estado `PARTIAL_WITH_NEXT_STEP` a estados canonicos y mapear `MissionStatus.PARTIAL` a ese estado.
- **Riesgo:** bajo (solo trazabilidad).
- **Rollback:** revertir ambos archivos.

### Cambio 3 (tests): endurecer matriz de edge-cases

- **Archivos:** `tests/test_agent_integration.py`, `tests/test_terminal_dispatch.py`, `tests/test_filesystem_dispatch.py`
- **Accion:** agregar tests de:
  - estados terminales por `MissionStatus` publico;
  - `terminal_run_command` verificacion incompleta/honestidad;
  - `filesystem_write_text` y normalizacion anti fake-success;
  - verifier `skipped/failed/unverifiable`.
- **Riesgo:** bajo.
- **Rollback:** revertir tests nuevos.

---

## Tests a ejecutar

1. Tests nuevos enfocados de esta pasada.
2. Subset previo del primer reporte.
3. Suite relevante:
   - `tests/test_agent_integration.py`
   - `tests/test_terminal_dispatch.py`
   - `tests/test_filesystem_dispatch.py`
   - `tests/test_verifier.py`
   - `tests/test_resolver.py`
   - `tests/test_security.py`
   - `tests/test_app_resolver.py`
   - `tests/test_app_open_verifier.py`

---

## Criterio de exito

- No se agregan features nuevas.
- Carter queda mas honesto/robusto ante fake success:
  - sin “hecho/listo” no verificable;
  - estados terminales de trace coherentes con `MissionStatus`;
  - edge-cases de terminal/filesystem/app-open cubiertos por tests.
- Cambios minimos, reversibles y acotados.

