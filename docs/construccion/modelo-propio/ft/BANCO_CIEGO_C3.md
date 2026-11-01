## Banco ciego c3: oficial frente a cand

Juez: claude (subagentes o claude -p, a ciegas). Criterio sha256 525da59c35ef…; 3 lecturas por misión y corrida.

| Métrica | oficial | cand |
|---|---|---|
| misiones comparadas | 160 | 160 |
| logrado (mayoría de 3) | 36 | 44 |
| límite honesto (mayoría de 3) | 51 | 51 |
| éxito falso (mayoría de 3) | 11 | 11 |
| fallo (mayoría de 3) | 62 | 54 |
|   de ellas sin mayoría (cuentan como fallo) | 3 | 6 |
| pass^3 (logrado en las 3) | 24 | 38 |
| misiones con algún éxito falso (alguna corrida) | 25 | 20 |
| «en las manos» (mayoría) | 0 | 3 |
| oráculo solo: ok por mayoría | 94 | 100 |
| oráculo solo: pass^3 | 79 | 92 |
| logrados por corrida | 34/160, 34/160, 36/160 | 45/160, 43/160, 47/160 |
| primera señal p95 (todos los turnos) | 35.62 s | 64.91 s |
| primera señal p95 (turnos que sonaron) | 31.29 s | 57.18 s |
| primera señal p50 | 3.68 s | 4.62 s |
| turnos con primera señal ≤ 3 s | 174/534 | 144/534 |
| turnos sin ningún sonido | 4 | 7 |
| primera respuesta p95 | 58.56 s | 79.12 s |
| duración de BAXY por misión, media (s) | 12.8 | 17.9 |
| duración de BAXY por misión, mediana (s) | 4.1 | 5.8 |
| duración del caso con setup y oráculos, media (s) | 52.4 | 54.9 |
| robos de foco (pasos; meta 0) | 0 | 0 |
| misiones con robo de foco | 0 | 0 |
| frente movido y devuelto (pasos, informativo) | 0 | 1 |
| pasos con teclado/ratón físicos (informativo) | 109 | 55 |

**McNemar** (oficial → cand, logrado por mayoría, 160 misiones pareadas): 9 sólo cand, 1 sólo oficial; p = 0.0215 (significativo a α 0,05).
**Meta del plan**: cand > oficial en logradas (44 frente a 36: sí); éxitos falsos ≤ oficial + 1 (11 frente a 11 + 1: sí); pass^3 ≥ oficial (sí). **CUMPLE**.
Misiones que gana cand: C3-006, C3-015, C3-057, C3-081, C3-096, C3-098, C3-105, C3-107, C3-141. Que pierde: C3-134.

**Por máquina** (máquina de cada semilla, s0/s1/s2; clases por mayoría de misión):

| Máquinas | Brazo | misiones | logrado | límite honesto | éxito falso | fallo | McNemar |
|---|---|---|---|---|---|---|---|
| portátil/portátil/portátil | oficial | 50 | 18 | 16 | 3 | 13 |  |
| portátil/portátil/portátil | cand | 50 | 20 | 15 | 2 | 13 | 2 sólo cand, 0 sólo oficial; p = 0.5000 |
| portátil/PC/PC | oficial | 110 | 18 | 35 | 8 | 49 |  |
| portátil/PC/PC | cand | 110 | 24 | 36 | 9 | 41 | 7 sólo cand, 1 sólo oficial; p = 0.0703 |

Cómo se mide: las clases las da juez_c3.py (CRITERIO_C3.md, a ciegas) y la mayoría por misión es la clase de 2 de las 3 corridas (sin ella, fallo); la primera señal es el primer sonido de cada turno desde su texto (aviso o respuesta, first_audio_ms de bench_e2e.py), p95 por rango más cercano y con los turnos que no sonaron como los más lentos; la duración de BAXY es la suma por turno del texto a su respuesta final (turn.end.ms); un robo de foco es un paso cuyo recibo dice que el frente pasó a otra ventana y no volvió (frontChanged sin frontRestored, frontReturnFailed, o restored false en una ráfaga de teclado o ratón), sin contar abrir o traer al frente la ventana pedida (app.open, window.*). Lo que no dice ningún recibo (una ventana que se pone delante sola, un paso que no informa del frente) no se ve.
