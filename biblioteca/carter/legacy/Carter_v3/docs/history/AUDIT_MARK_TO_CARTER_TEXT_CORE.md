# AUDIT MARK TO CARTER TEXT CORE

## 1) Resumen ejecutivo

- **Si, Mark aporta valor real**, pero en esta fase solo como inspiracion puntual para robustez operacional, no como arquitectura.
- **Adoptar ahora (nucleo texto):**
  - trazabilidad interna de estados de turno mas explicita y legible;
  - normalizacion defensiva de resultados de tools para prevenir falsos `COMPLETE` por respuestas vacias;
  - tests adicionales anti fake success (salida vacia/excepcion/estatus inconsistentes).
- **Backlog (no ahora):** voz, camara, UI/HUD, drag and drop, browser avanzado Playwright, file processor universal.
- **Prohibido copiar:** dependencia cloud obligatoria, `generated_code`, `Done` por defecto, hardcodes por app en el core, ejecucion riesgosa sin policy/verifier.

Conclusión: para el **nucleo texto actual** Mark aporta poco codigo reusable directo, pero si aporta patrones de operacion (estado/progreso) que pueden adaptarse de forma minima y segura en Carter.

---

## 2) Mapa tecnico de Carter_v3

### Modulos principales

- `src/carter_v3/agent.py`: loop central de turno.
- `src/carter_v3/contracts.py`: contratos publicos (`MissionStatus`, `VerifierStatus`, `AgentTurnResult`, `compute_mission_status`).
- `src/carter_v3/tools/*`: dispatch por dominios + verificacion.
- `src/carter_v3/security/policy.py`: clasificacion de riesgo y bloqueos.
- `src/carter_v3/resolvers/*`: intencion, lenguaje y resolucion de targets.
- `src/carter_v3/response_composer.py`: respuesta final basada en evidencia.
- `src/carter_v3/trace.py`: eventos estructurados por turno.
- `src/carter_v3/session_state.py`: contexto efimero seguro entre turnos.
- `tests/*`: cobertura amplia de rutas criticas.

### Flujo de turno texto (resumen)

1. input policy pre-LLM;
2. short-circuit de trivial/ambiguo;
3. clasificacion de intencion;
4. resolucion de target/contexto;
5. seleccion de tools permitidas;
6. llamada LLM + materializacion de steps;
7. ejecucion de tool + verificacion;
8. `compute_mission_status`;
9. compose reply basada en evidencia + guards finales.

### Parser/tool-calling

- Carter filtra calls por herramientas permitidas, forma esperada y riesgo.
- Soporta fallback estructural cuando LLM no emite tool call valida.

### Mission status / estados

- Publicos: `trivial`, `complete`, `partial`, `failed`, `needs_user`, `unverified`.
- `compute_mission_status` ya prioriza policy blocks, errores de motor y evidencia del verifier.

### Verifier / VerifiedOutcome

- `VerificationManager` mapea tool->verifier.
- estados: `confirmed/pending/failed/skipped/unverifiable`.
- buen baseline anti fake success (verificacion causal en `app_open`, checks post accion, fallback honesto).

### Policy / seguridad

- bloquea patrones destructivos/exfil.
- exige aprobacion para alto riesgo.
- no confia en `user_approved` inyectado por LLM.

### Resolver apps/recursos

- `ResourceResolver` + `AppResolver` + probes de procesos/ventanas.
- enfoque mas universal que hardcodes directos.

### Memoria

- `MemoryStore` con filtros de secreto y confirmacion contextual.
- flujo de `offer/confirm` para evitar guardar ruido.

### Tests existentes

- cobertura alta en `tests/test_agent_integration.py` y modulos de seguridad/verifier/resolver.
- ya hay pruebas de trivialidad, policy blocks, deictic targeting, unverified honesty y retries.

### Puntos debiles actuales (fase texto)

- trazabilidad de estados es buena pero no estandarizada en una secuencia canonica de alto nivel.
- posibilidad de anomalias de dispatch/verifier (tool `ok=True` vacia) requiere endurecimiento adicional.
- faltan tests explicitos de “resultado vacio no puede terminar en exito fuerte”.

---

## 3) Mapa tecnico de Mark-XXXIX-main

### Modulos principales

- `main.py`: loop principal (voz/audio + function calling + UI).
- `actions/*`: gran set de acciones (browser, file, system, apps, etc.).
- `agent/planner.py`, `agent/executor.py`, `agent/error_handler.py`, `agent/task_queue.py`.
- `ui.py`: experiencia visual/estado.

### Loop del asistente

- altamente acoplado a Gemini Live Audio + UI.
- tool dispatch con muchas rutas `result = r or "Done."`.

### Tools y manejo de acciones

- cobertura funcional alta, pero con fuerte mezcla de:
  - cloud LLM para orquestacion/analisis;
  - heuristicas por app;
  - fallbacks agresivos.

### Browser/File/System

- browser con Playwright y sesiones persistentes (potente pero fuera de fase actual).
- file processor “universal” grande y cloud-heavy.
- acciones de sistema amplias, con riesgo de verificabilidad heterogenea.

### Task queue

- existe (`agent/task_queue.py`) con estados `PENDING/RUNNING/COMPLETED/FAILED/CANCELLED`.
- idea util conceptualmente para progreso de tareas largas.

### Patrones de estados

- estados de UX (`LISTENING/THINKING/SPEAKING`) orientados a voz/UI.

### Dependencias externas

- acoplamiento elevado a Gemini (`google-genai` y `google-generativeai`) en muchos modulos.

### Lugares con posible fake success

- multiples `result = r or "Done."` en `main.py` y `agent/executor.py`.
- fallback a texto de exito aunque la evidencia sea debil o vacia.

### Lugares con generated code

- `agent/executor.py`: `_run_generated_code` + fallback de herramientas desconocidas a codigo generado/ejecutado.
- `actions/desktop.py`: ejecucion de codigo generado.

### Hardcodes por app

- `actions/open_app.py` contiene mapa extenso de aliases por app/OS.

### Riesgos de seguridad

- rutas con ejecucion dinamica/generacion de codigo;
- alta superficie de automatizacion sin misma rigurosidad de verifier estructural que Carter;
- dependencia cloud como pilar operativo.

---

## 4) Clasificacion de ideas de Mark

| Idea de Mark | Archivo/módulo donde aparece | ¿Sirve para núcleo texto actual? | Adoptar ahora / Backlog / Rechazar | Razón alineada con ContextoCarter.md | Riesgo | Cómo adaptarla estilo Carter |
|---|---|---:|---|---|---|---|
| Secuencia explicita de estados de ejecucion | `main.py`, `agent/task_queue.py` | Si | Adoptar ahora | mejora trazabilidad/progreso honesto sin UI | Bajo | estados internos canonicos en trace textual |
| Task queue con estados | `agent/task_queue.py` | Parcial | Backlog | util para misiones largas, pero fuera de foco actual | Medio | evaluar luego como extension de `mission_status` |
| `open_app` con resolucion multi-OS/aliases | `actions/open_app.py` | Parcial | Backlog | puede ayudar resolver universal, pero mapa hardcoded choca con valor 6/7 | Medio | usar discovery/resolver declarativo, no aliases core |
| Browser Playwright persistente | `actions/browser_control.py` | No (ahora) | Backlog | no corresponde a fase texto actual | Medio/Alto | solo en fase posterior, con verifier/policy de Carter |
| File processor universal | `actions/file_processor.py` | No (ahora) | Backlog | agrega complejidad y cloud; no core texto | Alto | descomponer en tools chicas verificables a futuro |
| Fallback `generated_code` | `agent/executor.py` | No | Rechazar | contradice seguridad y verificabilidad | Alto | no adoptar |
| Respuestas `"Done."` default | `main.py`, `agent/executor.py` | No | Rechazar | contradice “no mentir nunca” | Alto | respuesta siempre basada en evidencia/verifier |
| Dependencia Gemini obligatoria | multiples modulos | No | Rechazar | contradice local-first y privacidad | Alto | mantener adapters locales y externos opcionales |
| Error-recovery con intentos/replan | `agent/error_handler.py`, `agent/executor.py` | Parcial | Adoptar ahora (parcial) | idea util: degradar honestamente y dar siguiente paso | Bajo/Medio | fortalecer normalizacion de resultados y status |

---

## 5) Lista ADOPTAR AHORA (solo nucleo texto)

1. **Estados internos canonicos de turno en trace textual**
   - objetivo: mejorar trazabilidad y depuracion sin UI.
2. **Normalizacion defensiva de `ToolResult` + `VerifiedOutcome`**
   - objetivo: evitar exito falso cuando dispatch devuelve vacio/inconsistente.
3. **Tests anti fake success adicionales**
   - objetivo: blindar contra regresiones de “hecho/listo/completed” sin evidencia.

---

## 6) Lista BACKLOG FUTURO

- voz (STT/TTS, mute, duplex);
- camara/vision;
- UI/HUD;
- drag and drop;
- browser Playwright avanzado;
- file processor universal;
- resource monitor visual;
- experiencia Jarvis.

---

## 7) Lista NO COPIAR NUNCA

- dependencia cloud obligatoria (Gemini como nucleo);
- `generated_code` automatico;
- respuestas por defecto tipo `"Done."` sin evidencia;
- hardcodes por app dentro del core de decision;
- `assume-and-proceed` en acciones de riesgo;
- tools sin pasar policy;
- acciones sin verifier o con verifier debil para efectos reales;
- flujos que degraden privacidad/confianza del usuario.

