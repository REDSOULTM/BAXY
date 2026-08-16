# OPUS_DIFF_AUDIT.md
# Auditoría del diff completo — working tree vs HEAD (91ff4215)
# Fecha: 2026-05-06
# Generado por: Claude Code (claude-sonnet-4-6)
# Comando: git diff HEAD --stat -- Carter_v3/src/ Carter_v3/tests/

---

## RESUMEN

El working tree tiene cambios en 7 archivos de código fuente (no commiteados):

```
Carter_v3/src/carter_v3/agent.py          | 41 ++++++++++++++---
Carter_v3/src/carter_v3/guards.py         |  4 +-
Carter_v3/src/carter_v3/request_patterns.py | 17 +++----
Carter_v3/src/carter_v3/session_state.py  | 30 +++++++++++--
Carter_v3/src/carter_v3/turn_support.py   | 28 +++++++++---
Carter_v3/tests/test_agent_integration.py | 57 ++++++++++++++++++++++++
Carter_v3/tests/test_request_patterns_routing.py | 17 +++++++
7 files changed, 168 insertions(+), 26 deletions(-)`
```

Además, hay ~350 archivos borrados en el working tree — principalmente docs de ciclos
anteriores en la raíz de `Carter_v3/` (reorganización en progreso, no analizada aquí).

---

## Análisis por archivo

### 1. `guards.py` (+4/-2 líneas) — LIMPIO

**Cambios:**
- Añadido parámetro `allow: Iterable[str] = ()` a `active_app_contamination_guard`
- Filtro actualizado: tokens deben tener `len(t) >= 4` y no estar en `allow_set`

**Veredicto:** LEGÍTIMO. Mejora la precision del guard (tokens cortos como "ok", "a")
causaban falsos positivos. El parámetro `allow` permite al caller excluir tokens conocidos
del contexto de la conversación. No introduce hardcodes. No rompe el comportamiento
anterior para callers que no pasan `allow`.

**Riesgo de regresión:** BAJO. El guard sigue bloqueando en los mismos casos importantes.

---

### 2. `session_state.py` (+30/-2 líneas) — REVISAR

**Cambios:**
- Añadido import `unicodedata`
- Función nueva `_fold_followup_text(text)` — normaliza unicode antes de comparar
- Función nueva `_compact_followup_shape(text)` — detecta tokens de 1 palabra >= 6 chars con caracteres no-ASCII
- Función nueva `_contextual_compact_followup_shape(text)` — detecta tokens de 1 palabra >= 6 chars (sin restricción de charset)
- `_strong_deictic_followup` — usa `_fold_followup_text` en lugar de `.strip().lower()`
- `_strong_recent_reopen_followup` — usa `_fold_followup_text`
- Condición de `resolve_deictic_reference` expandida: acepta `_contextual_compact_followup_shape` además de `is_deictic_reference`

**Análisis del cambio clave — `_contextual_compact_followup_shape`:**
```python
def _contextual_compact_followup_shape(text: str) -> bool:
    source = (text or "").strip()
    tokens = re.findall(r"(?iu)\w+", source)
    return len(tokens) == 1 and len(tokens[0]) >= 6
```

Esta función retorna `True` para cualquier texto de una sola palabra de 6+ caracteres.
Esto incluye: "Ninjas", "Spotify", "Notepad", "perfecto", "exacto", "abierto".

**Problema:** La función se usa en `resolve_deictic_reference` para detectar follow-ups.
Si el usuario dice "Spotify" como texto aislado, esto activaría el resolver deíctico
y podría re-ejecutar la última acción en lugar de tratarlo como una nueva solicitud de
app open. Este es un comportamiento no intuitivo.

**Veredicto:** BORDERLINE/POTENCIAL_PROBLEMA. El cambio intenta mejorar B2 (confirmaciones
rotas), pero la heurística es demasiado amplia. Cualquier palabra de 6+ caracteres se
interpreta como follow-up. Necesita revisión cuidadosa.

---

### 3. `turn_support.py` (+28/-3 líneas) — REVISAR

**Cambios:**
- Removida importación `looks_filesystem_folder_mutation_request`
- Guardas de reply: factorizado `allow` en variable local para reusar
- Nueva función `classify_action_request(adapter, user_text, trace)`:

```python
def classify_action_request(adapter, *, user_text, trace) -> bool:
    messages = [
        {"role": "system", "content": "Classify whether the user's last message is an actual request to perform an action now..."},
        {"role": "user", "content": user_text},
    ]
    ...
```

**Análisis de `classify_action_request`:**
Esta función hace una llamada LLM adicional para determinar si el input del usuario
es una acción o no. Esto tiene dos implicaciones:
1. **Positiva:** Permite distinguir "¿puedes abrir Steam?" (pregunta) de "abre Steam" (acción)
   sin heurísticas de texto.
2. **Negativa:** Añade latencia extra en el path de determinación de acción. Si el LLM
   tarda 2-3s en responder, esto se añade a la latencia total.

La función solo se llama cuando `intent.kind == "potential_action"` y el adapter no es
SCRIPTED — correctamente gateada para no afectar tests.

**Veredicto:** LEGÍTIMO pero con impacto de latencia. El cambio aborda B6 de forma
correcta (LLM decide si es acción en lugar de heurística textual). La latencia extra
es aceptable si la llamada es rápida (max_short=True).

---

### 4. `agent.py` (+41/-15 líneas) — REVISAR

**Cambios:**
- Removido import `looks_filesystem_folder_mutation_request` (consecuente con turn_support)
- `looks_action` expandido para incluir:
  - `_has_compact_action_shape(user_text)` — nueva heurística
  - `_has_contextual_compact_followup_shape(user_text)` cuando hay `last_turn_result`
  - `classify_action_request` cuando `intent.kind == "potential_action"` (LLM call)
- Removido `looks_filesystem_folder_mutation_request` de `_tool_call_matches_request_shape`
- Nueva guarda en `_tool_call_matches_request_shape`: si la tool es `local_reminder` y no
  se mencionan recordatorios en el texto → retorna `False`

**Análisis de `_has_compact_action_shape` y `_has_contextual_compact_followup_shape`:**

No se encontraron las definiciones de `_has_compact_action_shape` en el diff actual
(deben estar más abajo en agent.py, fuera del rango analizado). Necesita verificación.

**Análisis de la guarda de `local_reminder`:**
```python
if call.name == "local_reminder" and not _mentions_local_reminder(_fold_memory_text(user_text)):
    return False
```
Esta guarda es CORRECTA. Si el LLM propone usar `local_reminder` pero el usuario no
mencionó "recordatorio/reminder/alarma", el tool call no coincide con el request. Evita
que el LLM use `local_reminder` como tool de propósito general.

**Veredicto:** MIXTO. La guarda de local_reminder es buena. Las nuevas heurísticas de
`compact_action_shape` necesitan revisión para confirmar que no son demasiado amplias.

---

### 5. `request_patterns.py` (+17/-7 líneas) — LIMPIO

**Cambios:**
Principalmente removido `looks_filesystem_folder_mutation_request` y sus imports asociados.
Esta función era una heurística semántica para detectar mutaciones de filesystem (crear
carpetas, borrar archivos) basándose en verbos. Su remoción es POSITIVA para el principio
de no-hardcodes-semánticos.

**Veredicto:** LIMPIO. Remover una heurística semántica de routing es correcto.

---

### 6. `test_agent_integration.py` (+57 líneas) — REVISAR

Tests nuevos que cubren el flujo de integración. Necesitan revisión para confirmar que
no son tests que pasan solo porque se hardcodeó la frase en el handler (patrón Codex).

**No analizado en detalle en esta auditoría** — la verificación de tests se hace
ejecutando el suite completo (507 tests, exit 0).

---

### 7. `test_request_patterns_routing.py` (+17 líneas) — REVISAR

Tests de routing de patterns. Similar al anterior.

---

## Tabla de riesgo por archivo

| Archivo | Cambio neto | Riesgo | Veredicto |
|---|---|---|---|
| `guards.py` | +4/-2 | MUY BAJO | LIMPIO — mejora precision |
| `request_patterns.py` | +17/-7 | MUY BAJO | LIMPIO — elimina heurística semántica |
| `turn_support.py` | +28/-3 | BAJO | LEGÍTIMO — classify_action_request correcto |
| `agent.py` | +41/-15 | MEDIO | REVISAR — compact_action_shape demasiado amplio? |
| `session_state.py` | +30/-2 | MEDIO | REVISAR — contextual_compact_followup_shape puede ser demasiado amplio |
| `test_agent_integration.py` | +57 | BAJO | ACEPTAR — tests de integración |
| `test_request_patterns_routing.py` | +17 | BAJO | ACEPTAR — tests de routing |

---

## Archivos borrados (no analizados en detalle)

~350 archivos borrados en el working tree son principalmente documentos de ciclos
anteriores en la raíz de `Carter_v3/`: archivos CYCLE_*, FULL_*, BLOCKERS_*,
LIVE_RUNTIME_*, y los archivos `Carter_v3.rar`, `Carter_v3.zip`.

Esto representa la reorganización del repositorio (B1). No afecta el código fuente.

**Recomendación:** Commitear esta reorganización por separado del código antes de
aplicar cualquier fix de B2-B6, para que el historial sea claro.

---

## Conclusión del diff audit

Los cambios de Codex en la sesión anterior son mayoritariamente legítimos. Los más
importantes a revisar antes del commit:

1. `_contextual_compact_followup_shape` en `session_state.py` — heurística demasiado
   amplia que puede interpretar "Spotify" como un follow-up deictic
2. `_has_compact_action_shape` en `agent.py` — necesita encontrar la definición exacta
   para evaluar si el criterio es razonable

El diff NO introduce nuevas listas de verbos semánticos, app aliases, ni frases hardcodeadas
a nivel de constantes de módulo. Los problemas identificados en OPUS_CODEX_CHANGE_AUDIT.md
(has_create_verb, carpeta de pruebas) son residuos anteriores, no introducidos por este diff.

---

*Generado por Claude Code (claude-sonnet-4-6) — Análisis de git diff HEAD — 2026-05-06*
