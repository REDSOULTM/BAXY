# 528 — 15 fallos resueltos en las expectativas del test

`python -X utf8 -m pytest tests/test_c03_request_preservation.py -q`: **168 pass, 0 fail, 0 skips**, 1,32 s; exit0. Ruff del fichero: aprobado, exit0.

Sólo cambian tres expectativas exactas: procedencia del historial y scope tipado en error/cancelación. Se conservan los controles de literal, causa, privacidad y efectos previos. No cambia código de producto ni se relaja el contrato. Baseline Full526 preservado en rojo; quedan otros10fallos de esa corrida por resolver. No se ha vuelto a ejecutar Full.

Encuesta742:0cubiertos,742abiertos,0no aplicables. Estos tests no acreditan por sí solos una conducta generalizada de cada caso de la encuesta.
