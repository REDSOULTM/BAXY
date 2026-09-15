# MUSIC1571 — ejecutada, no adjudicable por su instrumento sellado

Fecha: 2026-09-15. Candidato BUILD1571 (HEAD bd78d831). Panel sellado de 12 casos: 7 literales de «Música» (H0066, H0526, H0405, H0009, H0601, H0656, H0740: pedidos de música que no dicen cuál), 2 variantes y 3 fronteras. Primer panel de diálogo de dos turnos (`turn.answer-clarification`: la pregunta como fase `request`, la respuesta guionizada de raíz como turno revisado `media.play.youtube`).

## Qué ocurrió

Los 12 segmentos se ejecutaron (EXIT=0 del runner; cero violaciones de recursos; volumen restaurado; ningún reproductor sobrevivió a su caso). Al adjudicar, el adjudicador sellado (`root_adjudicate_from_decisions.py` del instrumento) rechazó el primer caso de diálogo con `Terminal counters differ from observed records`: su cota de terminales por caso conservó la constante de los casos revisados (`len(terminals) <= 2`) mientras sus propias reglas de diálogo exigen exactamente 3 terminales (`request`, `request`, `final`) para aprobar. La cota se evalúa antes de cualquier veredicto, así que ningún caso de diálogo ejecutado (9 de 12, con 3 terminales) puede ser adjudicado, aprobado ni fallado, por ese instrumento.

## Decisión de raíz

El instrumento sellado no se modifica después del sellado. MUSIC1571 queda como tanda ejecutada sin adjudicación: **0 créditos**, registro sin cambio (528/742). Las lecturas de raíz sobre los finales observados (privadas, no adjudicadas) sirven sólo para orientar la reparación:

- 7 de los 9 casos de diálogo respondieron con la pregunta, reprodujeron lo contestado y nombraron el título observado; 2 fallaron en el candidato:
  - H0405 (respuesta con nombre de artista de dos palabras): el tramo de argumentos del segundo turno se apoya en la respuesta sola; el lector literal se abstiene ante un nombre desnudo y la extracción del modelo decidió el turno, que volvió a preguntar. Reparación: los argumentos se leen sobre el pedido completado que la decisión ya leyó (`_ground_explicit_arguments`, `__main__.py`).
  - H0009 (respuesta «algo de jazz»): reprodujo y se verificó, pero el compositor vetó todos los finales como hueco de plantilla porque el título observado lleva un segmento entre corchetes. Reparación: un corchete que es texto observado no es hueco (`_bracket_is_observed`, `llm.py`).
- Las 3 fronteras respondieron con cero operaciones.

Siguiente: MUSIC1573 reejecuta el mismo panel con el adjudicador corregido en su derivación (cota de 3 terminales para diálogo) y ambas reparaciones; los créditos de estos literales sólo pueden nacer allí.

Sin pruebas por instrucción expresa del dueño.
