# LIVE_RUNTIME_POST_CLEANUP_BLOCKERS

Baseline: `LIVE_SAFE_RUNTIME_SMOKE_RESULTS_POST_CLEANUP.md`

Clasificación: solo fallos que se mantienen vivos tras el cleanup de hardcodes.

---

## A. prompt/persona/capabilities

### 1) Greeting typo tratado como “acción” ambigua
- Prompt: `HGOla`
- Respuesta exacta: `No encontré un objetivo claro y no voy a actuar sobre algo ambiguo. Dime la app, ventana, archivo o URL exacta.`
- Comportamiento esperado: `TRIVIAL` (chat seguro) con saludo tipo “Hola…”, sin rutas de acción/estado.
- Causa probable: `deictic_shaped`/`is_deictic_reference()` está clasificando palabras arbitrarias que terminan en `la/lo/los/las` como referencia deíctica, forzando la ruta de acción y luego ambigüedad.
- Por qué no puede arreglarse con hardcode: no es “HGOla especial”; es un falso positivo estructural (regla demasiado amplia).
- Fix universal propuesto: endurecer la detección de referencia deíctica para que solo matchee pronombres/deícticos gramaticales válidos (no palabras genéricas que terminan en `la`).
- Archivos: `src/carter_v3/request_patterns.py` (DEICTIC_REFERENCE / is_deictic_reference)
- Tests:
  - `tests/test_live_regressions_from_user_log.py::test_typo_greeting_is_not_action` (ajustar aserción si cambia de `needs_user` a `trivial`)
- Riesgo: medio (podría afectar seguimiento de follow-ups deícticos si el cambio es demasiado agresivo).

---

## D. pending intent

### 2) Lectura filesystem por ruta Windows no entra a flujo estructural
- Prompt: `lee C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\ContextoCarter.md que es?`
- Respuesta exacta: `Voy a leer el archivo. Un momento por favor.`
- Comportamiento esperado: ruta Windows -> tool `filesystem_read_text` (o estado honesto de permisos si la política bloquea), y que el siguiente `Sí` continúe el flujo si corresponde.
- Causa probable: el runtime actual no vuelve a habilitar “filesystem read por forma” (path Windows) en la síntesis/selección estructural de herramientas; el sistema termina en un follow-up/LLM-driven flow que no conserva ni ejecuta el pending intent como se requiere.
- Por qué no puede arreglarse con hardcode: debe operar por forma (path absoluto Windows), no por frase “lee”.
- Fix universal propuesto: reintroducir `extract_windows_path()` y usarlo para:
  - activar `looks_action` cuando exista path Windows;
  - seleccionar el tool `filesystem_read_text` cuando el path exista;
  - sintetizar `filesystem_read_text` cuando la LLM no produce tool calls.
- Archivos:
  - `src/carter_v3/request_patterns.py`
  - `src/carter_v3/agent.py`
  - `src/carter_v3/turn_support.py`
- Tests:
  - `tests/test_live_regressions_from_user_log.py::test_windows_path_plus_si_followup_works` (añadir aserción: que exista tool call `filesystem_read_text` para `r1`)
- Riesgo: medio (si la extracción del path es agresiva, puede interferir con URL/objetivos de otras herramientas).

---

## G. no capability available / H. response composer

### 3) Pregunta “para cuando tengo una alarma?” inventa estado futuro
- Prompt: `para cuando tengo una alarma?`
- Respuesta exacta: `No he configurado ninguna alarma. Si quieres, puedo notificarte cuando llegue a las 9 AM hoy. ¿Te interesa eso?`
- Comportamiento esperado: al no existir tool de alarmas, Carter debe evitar claims temporales/planificadas (sin fake success). Debe permanecer honesto: “no tengo capacidad X” o “necesito permiso/herramienta/alternativa”.
- Causa probable: `fake_success_guard` solo cubre afirmaciones tipo “listo/hecho/...”; no cubre “futuro con hora” cuando no hay evidencia/verificación de tool.
- Por qué no puede arreglarse con hardcode: no se trata de una frase específica; es una clase estructural de claim (tiempo futuro) sin confirmación de tool.
- Fix universal propuesto: extender guard estructural para detectar claims temporales (regex de hora/AM/PM) y marcar como violación si `any_confirmed == False` y no hubo herramientas confirmadas.
- Archivos:
  - `src/carter_v3/guards.py` (fake_success_guard + regex estructural de hora)
- Tests:
  - Nuevo test unitario en `tests/test_runtime_no_fake_success_live_cases.py` para el caso de “claim con hora futura sin tool”.
- Riesgo: bajo/medio (podría bloquear respuestas donde se menciona hora como contexto, pero solo cuando no hay confirmación de tool).

