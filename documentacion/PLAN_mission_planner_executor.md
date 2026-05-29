# Plan: Mission Planner-Executor — que el 4B complete tareas largas SIN subir de modelo

**Fecha:** 2026-05-27
**Objetivo de producto:** la app debe lograr lo que el usuario pida (sobre todo
movilidad/no_vidente: control 100% por voz, el agente hace TODO), con E2B-Q4 en
≤4GB. Sin cambiar de modelo.

## Diagnóstico (medido, no intuición)

La literatura (Plan-and-Act, arXiv:2503.09572; Task-Decoupled Planning,
arXiv:2601.07577) dice: para que un modelo chico complete tareas largas, la cura
NO es agrandarlo — es **separar planificación de ejecución** y dar **contexto
limpio a cada sub-paso** (evitar el "contexto enredado").

MEDIDO en este repo (no asumido):
- **Planificación**: el 4B descompone objetivos en sub-pasos **~70-90% bien**
  (7/10 en `_measure_4b_plan_results.json`; 2 de los 3 "fallos" son ruido del
  test, no errores reales). → La planificación NO es el cuello de botella crítico.
- **Ejecución**: planes correctos FALLAN al correr (visto en vivo: Instant Gaming,
  el `type` no enfoca la caja, el paso no surte efecto, el plan se aborta).
  → **La EJECUCIÓN paso-a-paso es el techo real.**
- Precedente de memoria: "el 4B NUNCA completa 2 acciones solo" — pero eso fue
  con ejecución frágil; con ejecución robusta el límite se corre.

## Conclusión de diseño

No hace falta un planner LLM más potente. Hace falta un **EJECUTOR DE MISIONES
ROBUSTO** que:
1. Toma el plan de sub-pasos (del `computer_use.plan_for` actual, que ya anda).
2. Ejecuta UN sub-paso a la vez con **contexto limpio** (no toda la historia).
3. **Verifica cada paso por estado del SO** (ya existe la cascada de capacidades).
4. Si un paso falla: **reintenta acotado** (re-captura pantalla, re-enfoca,
   re-intenta) ANTES de abortar.
5. Si tras los reintentos no puede: **avisa honesto dónde se trabó** (no delega).
6. Solo avanza al siguiente paso si el anterior quedó verificado.

Esto reusa: `computer_use.PlanExecutor` (ya ejecuta planes), `mission_checkpoint`
(reanudar), la cascada de capacidades `computer_use_caps/policy.py`, y las guardas
de accesibilidad (anti-delegación, continuación-en-turno).

## Fases con GATE (CLAUDE.md §2/§3)

### FASE 0 — MEDIR la ejecución (antes de construir)
Harness que corre misiones reales paso-a-paso y registra EN QUÉ paso se traba y
por qué (planificó mal / ejecutó mal / perdió contexto / verificación falló).
- **Lo hace el USUARIO** (toca GUI real; input sintético cierra VS Code).
- Yo armo el harness + un guion de misiones (simple→compleja).
- **GATE 0**: tener datos reales de ≥10 misiones antes de tocar el ejecutor.

### FASE 1 — Ejecutor robusto por paso
- Reintento acotado por sub-paso (re-snapshot + re-foco + re-intento, máx N).
- Contexto limpio por paso (no acumular la historia entera).
- Verificación dura por paso (ya existe; conectar al loop de reintento).
- **GATE 1**: en el set de Fase 0, las misiones que fallaban por "paso frágil"
  (no por planificación) suben a ≥80% completadas o fallo-honesto. Falso-PASS 0%.

### FASE 2 — Recuperación de planificación
- Si un paso es estructuralmente imposible (target no existe), **re-planificar
  ese tramo** con el estado actual (no toda la misión).
- **GATE 2**: misiones donde el plan inicial estaba incompleto se recuperan, sin
  loops infinitos (tope de re-plans).

### FASE 3 — Cierre honesto + checkpoint
- Reusar `mission_checkpoint` para misiones interrumpidas.
- Si no completa: reporte honesto del avance ("llegué hasta X de Y").
- **GATE 3**: nunca delega en el usuario (guarda anti-delegación ya existe);
  nunca afirma completar lo que no verificó.

## Límites honestos (no negociables)
- El 4B sigue siendo chico. Esto **corre el techo**, no lo elimina. Tareas de
  8+ pasos con apps sin UIA seguirán siendo frágiles.
- Medición física end-to-end = del usuario (input sintético cierra VS Code).
- NO subir de modelo (restricción de producto).
- Reusar lo que existe; no reconstruir.

## Fuentes
- Plan-and-Act: https://arxiv.org/abs/2503.09572
- Task-Decoupled Planning for Long-Horizon Agents: https://arxiv.org/pdf/2601.07577
