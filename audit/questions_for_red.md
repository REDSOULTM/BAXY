# Preguntas / pendientes para RED — sesión overnight 2026-05-21

Ordenado por urgencia. Cada item con el eje del norte rector afectado.

## 1. (BAJA — info) Boot E2E con llama-server quedó SIN validar en vivo
**Eje:** arquitectura. **Por qué:** `torch.cuda.is_available()` da False en este
intérprete (build CPU-only) y `nvidia-smi` mostró 6.7 GB ya en uso en la GPU con
el usuario potencialmente jugando. Levantar un modelo de ~6 GB encima arriesgaba
OOM-ear el proceso residente (CLAUDE.md mand. 6). **Recomendación:** cuando
liberes la GPU, corré `python -m gemma4_agent.launcher start-server` + medí tiempo
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

## 4. (INFO — no actioné) `_inbox` del agent_runner es una Queue() sin límite
**Eje:** fiabilidad. `submit()` encola turnos sin bound. En la práctica está
acotado por la tasa de input humano + el per-mode timeout (round 1) que evita
hangs indefinidos, así que NO lo consideré bug real (no hay productor runaway
plausible). Si alguna vez un wake-word con FP alto floodea comandos, podría
crecer. **Recomendación:** dejarlo como está salvo que veas el síntoma; un
maxsize con drop-oldest sería el fix, pero hoy es especulativo.

## 5. (INFO) Tracing con path de byte-null crashea (ValueError, no OSError)
**Eje:** fiabilidad. El fix de la ronda 7 captura OSError (full disk / permiso /
parent-es-file — los fallos REALES). Un path con `\0` embebido tira ValueError
antes, que NO se captura. NO es alcanzable en prod (ningún config genera un null
byte en un path). Lo dejé así a propósito: ampliar el except a ValueError
escondería bugs de programación legítimos. Anotado por completitud.

---

Sin BLOCKED_NEW_DEP esta sesión (no necesité instalar nada). Sin tradeoffs.md
(ningún fix mejoró un eje degradando otro — todos fueron lifecycle/teardown puro).
