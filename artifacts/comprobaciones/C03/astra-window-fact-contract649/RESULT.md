# 649 — el contrato no conserva todavía instalación, ventanas y alcance

El validador actual acepta las once respuestas ensayadas. Cuatro respetan los hechos y siete no, por lo que el contrato acierta 4/11. Un caso es el borrador real publicado en647; los otros diez son controles declarados, no resultados generados por un modelo ni turnos de producto.

Con installed=true y visibleWindowCount=0, pasan tanto «Spotify is not installed» como cifras de dos/tres ventanas. También pasan afirmaciones de que el proceso está ejecutándose y de que no está ejecutándose, aunque no se observó liveness en ningún sentido. Las respuestas que se limitan a instalación/ventanas o reconocen que no se comprobaron procesos se aceptan correctamente. Los controles se repiten en español e inglés.

La siguiente reparación debe conservar esos campos y el alcance de la observación. Bloquear únicamente running no resolvería las contradicciones de los otros casos. Herencia directa: `_payload_fact_defect` ya protege nombre de cuenta, volumen y reloj; las nuevas observaciones de aplicación aún no tienen una comprobación equivalente. Sin cambiar fuente, modelo, perfil, umbrales ni cobertura; encuesta25/717/0. Full646 continúa separado.
