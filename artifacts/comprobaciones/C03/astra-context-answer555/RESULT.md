# Tramo555 — interpretación interna separada de respuesta visible

La captura nativa543:27 produce direct_answer idéntica a «Eso era todo, gracias.» y resolved_meaning «El usuario ha indicado…». El código descartaba el eco y publicaba ese segundo campo. Se elimina únicamente esta alternativa: sólo direct_answer puede publicarse; si no sirve, se usa el reintento directo acotado que ya existía y se conserva ValueError si vuelve a fallar. Sin plantilla visible, capa nueva ni cambio de modelo.

Test-first5 fallos/1pass; focal6pass0,67s. Dueñas iniciales2fallos/1934pass mostraron pruebas antiguas que exigían publicar resolved_meaning; se actualizaron para exigir el reintento, la causa original y una respuesta dirigida a la persona. Dueñas finales1936pass+121subtests,0skips,17,15s. STT12pass/1skip ambiental,1,32s. Fast verde, Release21,57s,0advertencias/errores. Ruff de las dos pruebas después de corregirlas verde. Árbol STT actual5a3d37d79c0e4b7366c3d7857b699a32c9d6e1b84df9d794f89bc3dea890415d/403archivos; históricos intactos. SóloPython; Full final pendiente.

Encuesta7cubiertos/735abiertos/0NA, sin crédito aún para despedida: falta producto556. Preparada una corrida aislada con contexto CPU/volumen, despedidasES/EN y recuerdo literal, sinUI/voz. No reabrir BAXY manualmente.

554 no llegó a lanzar el modelo: su preflight esperó20 escritores y encontró18 porque la despedida iba por otro resolvedor. Esa diferencia permitió identificar la transformación errónea de555. No se adjudica calidad ni recursos aGemma554; la comparación no se ejecutó y deja de ser el siguiente paso.
