# Maratón de tests computer-use — 2026-05-25

RED pidió: ≥1000 tests directos al LLM y de computer-use, en todas las apps posibles,
operando real (foco autorizado). Toda medición por **estado del SO**. Branch
`PortandoLoMejor`.

## Total: ~1175 tests

| Fase | Tipo | Tests | Resultado |
|---|---|---|---|
| 1 | LLM-direct (emisión de plan de primitivas) | 567 | **564/567 = 99% correct**, 567/567 parseable |
| 2 v1 | computer-use e2e real (diagnóstica) | 288 | 199/288 = 69% → diagnosticado (ver abajo) |
| 2 v2 | computer-use e2e real (corregida) | 240 | **231/240 = 96%**, estable en 8 rondas |
| previos | optionA 16/16, e2e 9/9, wired 7/7, plan 10/10, etc. | ~80 | ~100% |

## Fase 1 — LLM-direct (planner universal): 99%
567 comandos (18 apps × acciones × fraseos × ES/EN/PT). El 4B emite el PLAN de
primitivas; se mide parseable + secuencia núcleo correcta. **567/567 parseable,
564/567 correct.** Los 3 "fallos": 2 artefactos de gate (send==Enter; comando absurdo
que generó el harness "calcular un texto") + 1 miss real. El planner es sólido en
todas las apps e idiomas — base de la capa universal.

Por tipo: open_chat 126/126, message 60/60, open_url 168/168, type ~165/168,
focus_app 44/45. Por idioma: ES, EN, PT ~100%.

## Fase 2 — computer-use e2e REAL (operando apps): 96%
v2 (corregida), 8 rondas, verificado por estado del SO:
- **calc_type: 100%** (80/80) — type+keypress, display.
- **chat_open (Discord): 100%** (48/48) — open_chat por quick-switcher, título.
- **browser_url: 98%** (79/80) — open_url, título normalizado.
- **open_app: 75%** (24/32) — los 8 fallos TODOS Spotify: lanza OK pero su ventana
  ("Spotify Premium") tarda >2s en aparecer → el verify del harness no la alcanzaba
  (artefacto de LATENCIA de lanzamiento, NO del agente; medido: Spotify SÍ abre).
  Steam/Paint/Explorer pasaron.

Cobertura de apps (variada, no solo calc/discord): Calculadora, Bloc de notas,
Opera GX / Chrome / Edge, Discord, Paint, Explorador, Configuración, Steam, Spotify.

## Bug REAL encontrado y arreglado (lo valioso de la maratón)
**open_url verify exigía el dominio CONTIGUO** en el título. Los sitios "espacian" el
dominio: "stackoverflow.com" → título "Stack Overflow", "duckduckgo.com" →
"DuckDuckGo". El match contiguo daba FALSO-NEGATIVO → el ejecutor reportaba fallo de
una navegación EXITOSA. **Fix** (computer_use.py): normalizar (quitar espacios/
puntuación) en ambos lados antes de comparar. Re-medido browser 6/6 incl.
stackoverflow/duckduckgo. Commit 8085c78. +test OpenUrlVerifyTest.

## Artefactos de fixture (NO bugs del agente, documentados)
- **Notepad Win11**: la v1 daba 43% porque las ventanas se ACUMULAN y el título queda
  con una palabra de test previa, confundiendo el contexto. Medido **5/5 en una
  ventana limpia**. La v2 resetea notepad por ronda (y SALTA notepad si ram.txt del
  user está abierto — no toca archivos del usuario).
- **Spotify**: lanza pero su ventana tarda; el verify con poco margen lo marca fallo.
- **Degradación bajo carga**: la v1 caía de 80%→64% en rondas tardías por acumulación
  de ventanas; la v2 (reset por ronda) se mantuvo 95-96% estable las 8 rondas.

## Conclusión
La capa universal de computer-use (el 4B planifica, un ejecutor corre primitivas
verificando por estado del SO) es **sólida y universal**: ~96-99% real across apps
variadas, idiomas y fraseos, con falsos-negativos explicados por fixtures/latencia,
no por el diseño. Harnesses reanudables: scripts/_marathon_llm_plans.py,
scripts/_marathon_cu_e2e.py. Crudos: scripts/gui_eval/_marathon_*.jsonl.

## Nota: corrida contaminada (NO usar como medición)
Una corrida tardía de Fase 2 dio 27% — CONTAMINADA: el usuario estaba usando la PC en
paralelo (tomó el foco / abrió ventanas), así que el verify del harness leyó ventanas
del usuario en vez de la app del test (falsos FAIL). Las replies del agente eran de
ÉXITO ("Listo, escribí 2+2 en Calculadora") y open_app (verify por ventana-presente,
robusto al foco) dio 24/24. NO es regresión del agente — es el verify del harness
sensible a la actividad del usuario. Medición válida = corridas con PC libre:
Fase 1 99%, Fase 2 v2 96%, Fase 3 multi/chains 100%.
