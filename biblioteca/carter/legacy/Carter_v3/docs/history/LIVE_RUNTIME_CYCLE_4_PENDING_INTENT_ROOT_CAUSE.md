# LIVE_RUNTIME_CYCLE_4_PENDING_INTENT_ROOT_CAUSE

Objetivo: explicar por qué `test_pending_intent_followups` pasaba mientras el smoke live seguía fallando en:

1. `lee C:\...\ContextoCarter.md que es?`
2. `Sí`

Sin hardcodes y con evidencia.

---

## 1) Qué pasa en el test que sí pasaba

Referencia: `tests/test_pending_intent_followups.py`.

- Turno 1 ejecuta `ToolCall(name="filesystem_read_text", arguments={"path": ...})`.
- El test fuerza un `VerifiedOutcome` inicial no concluyente (`UNVERIFIABLE`) para ese tool.
- El runtime guarda pending intent estructural (`SessionState.pending_intent`) con:
  - `call.name = "filesystem_read_text"`
  - `call.arguments["path"] = ...`
  - `turns_remaining = 2`
- En el turno 2 (`"Sí"`), el engine consume pending antes de la ruta trivial y re-ejecuta `filesystem_read_text`.

Resultado esperado del test: segundo turno no cae en trivial, sino que consume pending y vuelve a ejecutar el tool.

---

## 2) Qué pasaba en live real (evidencia)

Referencia: `LIVE_RUNTIME_CYCLE_4_PENDING_REPRO.md` (sección `stdin utf-8`).

### Observado en live (subprocess REPL con stdin UTF-8)
- Turno 1 sí ejecuta `filesystem_read_text` y sí guarda pending.
- El segundo input, enviado como `"Sí"` en UTF-8, llega al proceso REPL como mojibake: `user_text='SÃ\xad'`.
- En debug:
  - `has_pending_before=True`
  - `pending_candidate_result=miss`
  - pending se limpia
  - cae a ruta trivial

Conclusión: **el estado pending existía**, pero el segundo turno no lo consumía porque el texto de confirmación llegaba corrupto por encoding en el harness.

### Confirmación cruzada
- Mismo repro, pero enviando stdin en `cp1252`:
  - `user_text='Sí'`
  - `pending_candidate_result=hit`
  - `short_circuit_route=pending_intent_execute`
  - segundo turno vuelve a ejecutar `filesystem_read_text`.

---

## 3) Diferencias exactas test vs live/harness

### Test unitario
- llama `engine.run_turn("Sí")` dentro del mismo proceso Python;
- string Unicode intacto;
- pending candidate hace `hit`.

### Harness `audit/smoke_live_cycle_3.py` / `audit/smoke_live_post_cleanup.py` (antes del fix)
- ejecutaba REPL por subprocess;
- enviaba stdin con `encode("utf-8")`;
- proceso receptor interpretaba stdin con codepage local (`cp1252`);
- `"Sí"` llegaba como `SÃ­`.

### `Run_Carterv3.py` interactivo real
- reutiliza el mismo `Engine` y `SessionState` (no reinicia por turno).
- divergencia no era por pérdida de sesión, sino por **encoding de entrada del harness**.

### Engine/SessionState real
- pending se guardaba correctamente tras turno 1;
- pending se consultaba antes de trivial;
- fallo se producía por miss en candidate debido a input mojibake en turno 2.

---

## Root cause final

La divergencia test-vs-live era **principalmente de harness/encoding**, no de arquitectura core:

- el smoke runner enviaba prompts UTF-8 a un REPL que interpretaba stdin con codepage local;
- `"Sí"` se corrompía (`SÃ­`);
- `pending_intent_candidate` no lo reconocía como follow-up corto válido;
- pending se limpiaba y el turno caía en trivial.

Fix mínimo correcto: ajustar el runner (no hardcode) para codificar stdin con encoding local (`locale.getpreferredencoding(False)`), además de mantener instrumentación estructural para auditar pending lifecycle.

