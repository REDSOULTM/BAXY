# 397 — idioma conservado sin confundirlo con nombres

La guardia de respuesta ya no interpreta una tilde aislada como palabras
españolas en una frase inglesa. Reutiliza la lectura única para distinguir el
aporte léxico; conserva «Sí» y otras palabras españolas con tilde, y deja neutral
un nombre aislado. El umbral y la política de mezcla explícita no cambian.
Se añadieron tres construcciones funcionales («me llamo», «te llamas», «se llama»)
al lector de idioma, sin extraer nombres ni convertirlas en acciones.

La revisión encontró una regresión antes de medir producto: el conteo por
substring confundía «white llamas»/«These llamas» con las frases españolas.
El conteo existente de frases ES/EN exige ahora palabras completas.
Se conserva toda la evidencia de esa primera implementación; su verde no se
presenta como la validación de la versión final.

- Baseline: 7 failed, 12 passed, 226 deselected, 0,60s.
- Primer focal: 19 passed, 0 skips, 226 deselected, 0,35s.
- Nuevos controles de límites antes de corregirlos: 2 failed, 19 passed,
  226 deselected, 0,54s, baseline-phrase-boundary.log.
- Focal final: 21 passed, 0 skips, 226 deselected, 0,29s.
- Cinco suites Python dueñas finales: 1364 passed, 0 skips, 6,14s.
- `scripts/test_source_quality.ps1`: Fast final verde; build Release 1,22s,
  cero warnings y errores. Validación previa conservada: 1362 pass y Fast1,33s.

Comandos: focal con `python -m pytest tests/test_request_reading.py -q -k
'naming or accented_name'`; dueñas con test_turn_policy, test_compose_contract,
test_llm_transport, test_request_reading y test_price_v8_veto_damage_by_cause.
Pin de llm.py actual actualizado; evidencia y veredicto V8 sin cambios.

Fuente397 no modifica los prompts, el modelo, las operaciones ni el compositor
de resultados privados. 398 medirá el turno real de393b y variantes; no se
declara arreglada la respuesta por pasar tests. Sin Full durante reparación.
