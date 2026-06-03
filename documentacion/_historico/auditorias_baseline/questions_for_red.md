# Preguntas / pendientes para RED — sesión overnight 2026-05-21

Ordenado por urgencia. Cada item con el eje del norte rector afectado.

## 1. (BAJA — info) Boot E2E con llama-server quedó SIN validar en vivo
**Eje:** arquitectura. **Por qué:** `torch.cuda.is_available()` da False en este
intérprete (build CPU-only) y `nvidia-smi` mostró 6.7 GB ya en uso en la GPU con
el usuario potencialmente jugando. Levantar un modelo de ~6 GB encima arriesgaba
OOM-ear el proceso residente (CLAUDE.md mand. 6). **Recomendación:** cuando
liberes la GPU, corré `python -m gemma4_agent.infra.launcher start-server` + medí tiempo
a primera respuesta y que `boot_progress` reporte stages. El path ya está
auditado limpio (rondas 1/6) y cubierto por tests mockeados; solo falta el E2E.

## 2. (BAJA) Archivo desconocido sin trackear: `gemma4_agent/ContextoClaude.md`
**Eje:** ninguno (higiene). Apareció en `git status` (fecha May 20, anterior a
esta sesión — NO lo creé yo). 171 KB. No lo toqué (CLAUDE.md: no borrar lo que no
creé). **Pregunta:** ¿es intencional? Si es scratch, conviene gitignorearlo o
borrarlo. Si es contexto que querés versionar, agregalo.

## 3. (INFO) `middle_ellipsis` tenía un overflow de +3 en límites chicos
**Eje:** latencia. Lo tightené (ahora STRICTLY <= limit a cualquier tamaño) en el
commit del smoke. NO era un bug de runtime (los límites de prod son grandes), pero
el contrato decía "never grows" y no lo cumplía en el fallback. Ya resuelto, lo
anoto para que sepas que el primitivo cambió levemente (los tests round-7 siguen
verdes).

## 4. (DECISIÓN DE RED — comportamiento visible) `_inbox` del agent_runner sin límite
**Eje:** fiabilidad vs UX. `submit()` encola turnos sin bound. En el threat model
realista NO leakea: un turno se drena y procesa serialmente antes de que llegue el
siguiente input humano, y el per-mode timeout (round 1) evita hangs. El único
vector de flood es una tormenta de wake-FP — que es un bug a arreglar EN LA FUENTE,
no acá. **Por qué necesita a RED:** la única "mejora" sería un bound, pero acotar
una cola de TURNOS DE USUARIO con drop-oldest los descarta SILENCIOSAMENTE (viola
"never degrade silently"), y rechazarlos con señal visible es un cambio de
comportamiento de UI. Ninguna opción es un fix unilateral seguro.
**Pregunta refinada (1 línea):** ¿querés un bound duro en `_inbox` (ej. 32) que
RECHACE con un toast "estoy ocupado, repetí" — o lo dejamos unbounded (seguro hoy)?

## 5. ✅ RESUELTO (commit 2e9a48f) — Tracing con path malformado
Era: `__post_init__` capturaba solo OSError; un path con null byte tira ValueError
y crasheaba el constructor del agente. **Resuelto:** amplié a `(OSError,
ValueError)` SOLO en `__post_init__` (el boundary del filesystem). Razonamiento:
el diagnóstico jamás debe crashear lo que traza, y la clase de excepción es
irrelevante al preparar un path; NO esconde bugs de lógica (es IO, no agente).
Test nuevo `test_construct_on_malformed_path_disables`.

---

## Items que quedan para RED (resumen)
- **#1** boot E2E con GPU libre (cuando puedas, no es bug).
- **#2** ¿gitignorear/borrar `gemma4_agent/ContextoClaude.md`? (no lo toco: no lo creé).
- **#3** info (ya resuelto en su momento, sin acción pendiente).
- **#4** decisión de producto sobre el bound de `_inbox` (pregunta de 1 línea arriba).

BLOCKED_NEW_DEP (sesión de continuación): `hypothesis`, `pytest-cov`/`coverage`
NO están instalados. Fase 2 cae a tests table-driven; Fase 3 a análisis manual de
coverage. Si querés property-based + coverage automatizado, autorizá instalarlos.
Sin tradeoffs.md (el fix de #5 fue mejora pura de fiabilidad, sin degradar ejes).
