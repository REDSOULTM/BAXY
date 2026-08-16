# Arqueología del planner: Carter → BAXY Python → BAXY .NET

Fecha de corte: 2026-07-16. Esta arqueología no trata a «BAXY» como una sola
etapa. Se revisó la línea completa disponible en el workspace y en los
manifiestos históricos.

## Generaciones encontradas

| Generación | Camino real | Cómo resolvía misiones | Resultado útil | Brecha comprobada |
|---|---|---|---|---|
| Carter | `legacy/legacy_export`, arqueología de Carter v5 en `documentacion/agentes` | Bucle LLM actuar-observar, composites amplios, `MissionGoal` y planner/router principalmente heurístico | Estados explícitos, loop detector, jerarquía API/Win32/UIA/visión | Un composite podía producir el efecto varias veces; policy sobre la fachada equivocada; goal por categoría y no por target; confirmaciones no ligadas ni recuperación exact-once |
| Primer BAXY Python | `legacy/core`, `legacy/main.py` | Router y dispatcher de una capacidad; `splitter` dividía una orden antes de cualquier coordinación general | Shortlist, `no_tool`, degradación local y separación conversación/acción | Una orden compuesta se convertía en cláusulas independientes; no existía un plan padre confiable |
| BAXY Python, Tool Ecosystem v2 | `legacy/tooling`, `legacy/core/tooling_v2_*` | 39 workflows declarativos y `MissionEngine` durable con DAG inmutable, referencias tipadas, confirmación, leases, recovery, verifier y budgets | Es el activo histórico más valioso: ejecución durable, policy y verificación separadas del modelo | El grounding natural seguía siendo grande y heurístico; la composición general no se conectó antes del splitter. Steam+Spotify quedó especial-cased. El coordinador jerárquico fue diseñado, no integrado |
| BAXY .NET anterior a este corte | `src/Baxy.*`, `src/baxy_mind` en `3db92e1` | Core tipado y verificable de una operación; mente podía rutear una acción o hasta dos tool calls de chat | Frontera NativeAOT segura, riesgo/confirmación/verificación por operación, journal durable | No había planner, dependencia entre outputs, checkpoint de plan ni recuperación multipaso. La mente leía además una foto antigua de 21 tools aunque el core publicaba 102 |
| BAXY .NET, corte actual | `src/baxy_mind/planner.py`, `src/Baxy.Kernel/Planning`, `src/Baxy.App` | Planner híbrido acotado, doble pasada concordante, DAG forward-only, grounding diferido y ejecución por el core | Conserva las guardas actuales y recupera los mejores contratos del v2 sin portar su monolito | Las composiciones privadas `memory.*` siguen deliberadamente fuera del planner general; operaciones externas siguen sujetas a sus gates físicos |

## Qué decía realmente el corpus

El corpus congelado contiene 2.084 misiones y 14.836 mensajes. De las 263
misiones humanas etiquetadas, 166 requieren al menos dos familias de operación.
La longitud observada es:

| Operaciones | Misiones humanas |
|---:|---:|
| 0 | 45 |
| 1 | 52 |
| 2 | 93 |
| 3 | 42 |
| 4 | 16 |
| 5 | 9 |
| 6 | 3 |
| 7 | 1 |
| 9 | 1 |
| 15 | 1 |

El máximo histórico humano es 15. Por eso el contrato actual admite 16 pasos,
no 64: un paso de margen cubre el corpus sin convertir un benchmark hipotético
en alcance de producto.

Hay 14 registros multipaso que incluyen memoria privada; 12 mezclan además
otra familia y dos son exclusivamente privados. Buena parte proviene de logs
de ingeniería contaminados, pero se conserva el conteo honestamente. Estos
casos no autorizan a exponer `memory.*` al LLM: el parser y el envelope privado
siguen resolviéndolos antes del planner general o fallan cerrados.

## Activos recuperados y decisiones

- De Carter se conserva el principio actuar → observar → verificar, no su
  executor ni sus composites.
- Del primer BAXY se conserva la shortlist y la abstención, no el splitter como
  raíz de una misión.
- De Tool Ecosystem v2 se recuperan el DAG inmutable, outputs como referencias,
  checkpoints, confirmación, estado inconcluso y replanificación acotada.
- Del BAXY .NET actual se conserva el core como única autoridad. El modelo no
  declara riesgo, confirmación, retry, éxito ni permisos.
- Se descartó CodeAct/código arbitrario porque rompería el catálogo cerrado,
  la frontera NativeAOT y la autoridad del core.
- Se descartó un loop ReAct abierto. La observación sólo puede activar
  grounding de un paso ya aprobado o una replanificación acotada y segura.

## Brechas históricas convertidas en regresiones

- Catálogo de runtime: el sidecar recibe las 168 capacidades del `hello`
  autenticado; ya no lee la fixture antigua de 21.
- Efecto incierto: nunca se reintenta ni replantea automáticamente si
  `EffectMayHaveOccurred=true`.
- Salida no confiable: web, OCR, documento y títulos libres no vuelven al
  planner; sólo IDs, revisiones, hashes y estados permitidos.
- Plan parcial: si el planner disponible falla, no cae al router de una sola
  acción.
- Inestabilidad: propuesta y revisión deben conservar exactamente la misma
  secuencia de operaciones.
- Coerción por schema: la extracción puede abstenerse; enums e IDs requieren
  evidencia en el objetivo u observaciones verificadas.

## Evidencia física exploratoria

Se ejecutaron cinco iteraciones del mismo gate de seis casos sin invocar tools.
La primera salida útil obtuvo 0/6 por contrato. Las iteraciones revelaron plan
parcial, strings inventados, sustitución Spotify → Notepad y mezcla compra →
instalación/tarea. Cada hallazgo produjo una guarda determinista, no una
relajación del validador.

La batería diagnóstica terminó 6/6: conversación, app→audio, search→hash,
captura→OCR, compra prepare→commit y Spotify→volumen. En la compra, AppID y
precio estaban escritos literalmente; el plan no evita la confirmación
monetaria del core. Cero tools se ejecutaron.

El corpus completo se auditó después. De 166 misiones, 123 son objetivos
naturales evaluables, 29 son trazas contaminadas y 14 cruzan la frontera
privada. El baseline real fue 38 planes, 20 aclaraciones, 12 conversaciones y
53 rechazos contractuales seguros. La recuperación final, sin relajar el core,
obtuvo **47 planes, 61 aclaraciones, 15 conversaciones y cero errores**. Hubo
cero errores de proceso, cero operaciones privadas aceptadas y cero tools
ejecutadas. Evidencia: `historical_compound_audit.json`, los snapshots
`historical_planner_gate.before_*.json` y `historical_planner_gate.json`.
