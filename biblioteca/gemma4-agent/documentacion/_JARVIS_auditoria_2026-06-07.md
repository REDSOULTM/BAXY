# Auditoría capa Jarvis — 2026-06-07

Auditoría adversarial multi-agente (42 agentes: 7 dimensiones × auditor + verificador
adversarial + síntesis). **33 hallazgos confirmados** (pasaron verificación
adversarial). Reporte crudo completo: `_auditoria_jarvis_2026-06-07.json`.

Disparador: el user reportó que Jarvis ofrecía rutinas FALSAS ("cuando abrís
Spotify, abrís Disney") apenas abría una app. Tras arreglar lo visible, se auditó
todo el subsistema para hallar fallas latentes.

## ARREGLADO en esta sesión (7 fixes)

### CRITICAL
- **corruption-recovery brickeaba la DB en Windows** (`behavior_log.py`): el handle
  SQLite fallido no se cerraba antes del rename → WinError 32 → `_disabled=True`
  → Jarvis muerto sin recuperarse. FIX: `conn.close()` antes del rename + mover
  sidecars `-wal`/`-shm`.

### HIGH
- **"olvidate de todo" NO borraba todo** (`taste_profile.py::forget`): borraba solo
  `app_focus`/`media_play`, dejaba `app_open`/`app_close`/`boot` → el miner seguía
  minando tras un olvido confirmado (viola privacidad, que es ley). FIX: borra TODO
  el comportamiento del usuario.
- **boot → cron @09:00** (`pattern_miner.py::to_routine_trigger`): "cuando arrancás
  la PC, abro X" se programaba para las 9 AM (no al arranque) porque no hay trigger
  de logon real. FIX: boot devuelve None (no ofrecer lo que no se cumple) +
  `suggestion_queue` filtra candidatos no-mapeables.

### MEDIUM
- **oferta proactiva intrusiva** (`agent.py::_maybe_proactive_suffix`): se anexaba a
  CUALQUIER turno, incluso tras ejecutar una acción ("apenas abro la app actúa").
  FIX: solo ofrece en turnos conversacionales (sin tool ejecutado este turno).
- **perfil ruidoso** (`taste_profile.py`): `apps_by_slot` y `music_slots` no tenían
  umbral anti-ruido → 1 sesión declaraba un "hábito" falso que el LLM tomaba como
  verdad. FIX: `apps_by_slot` exige `_MIN_APP_DWELL_S`; `music_slots` exige
  `_MIN_MUSIC_SLOT_SESSIONS=3`.
- **`_enabled()` acoplado al safety flag** (`ambient_observer.py`): el fix del día
  anterior usaba `GEMMA4_AGENT_SAFETY=0` como proxy de test, pero safety es un
  toggle de producto que el user puede apagar → perdería Jarvis. FIX: señal
  dedicada `GEMMA4_DIAG=1` + `PYTEST_CURRENT_TEST` (robusto, precedente del repo).
  Los harnesses de diag setean `GEMMA4_DIAG=1` (boot harness + 38 scripts _diag).
- **latencia del miner** (`agent.py`): corría sobre TODO el historial cada turno.
  FIX: ventana de 30 días (`events(since_ms=...)`).

Tests: **55/55 verde** (2 actualizados al comportamiento correcto + 2 nuevos que
documentan los fixes de boot/forget).

## BACKLOG (LOW confirmados — no urgentes, ver JSON para detalle)

- `ambient_observer.py`: dwell usa wall-clock sin detectar sleep/lock/idle
  (hibernación infla horas); dedup de media solo vs fila anterior (micro-variantes);
  `stop()` nunca se llama (flush del app actual muerto); `_now_playing()` en `start()`
  bloquea el arranque.
- `behavior_log.py`: `events()` revienta con JSONDecodeError ante context malformado;
  `record()` devuelve True aunque INSERT OR IGNORE descarte; `prune()` sin VACUUM.
- `taste_profile.py`: `_clean_app` devuelve nombre crudo si el base queda vacío;
  dedup de sesión de media solo mira fila anterior.
- `pattern_miner.py`: target `cmd` se ofrece pero falla al aceptar; `count` se infla
  con re-aperturas; sin control de confounders (correlación causal falsa A↔B por 3ra
  causa); orden de palabras alemán en `describe('de')`.
- `agent.py`: handshake sí/no por keywords podría matchear un "sí" en medio de una
  frase larga; cooldown se consume antes de mostrar la oferta.
- `suggestion_queue.py`: guardado no atómico; `_load` traga toda excepción.

## Método
Cada hallazgo: auditor lee código real + data real → verificador adversarial
escéptico confirma/descarta (los falsos positivos se filtraron). Severidad
re-evaluada por el verificador (varios HIGH→MEDIUM, MEDIUM→LOW al medir impacto real).
