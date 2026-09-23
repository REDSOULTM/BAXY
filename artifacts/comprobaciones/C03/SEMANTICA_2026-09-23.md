# Fase 3.5 — semántica total: informe de cierre (2026-09-23)

Rama `codex/kiro-goal-c03`, desde `opus55-inicio` (b5c9fe72). Meta: `META_SEMANTICA_TOTAL_2026-09-22.md`.
Detalle vivo: `SEMANTICA_PROGRESO.md`; decisiones sin el dueño: `DECISIONES_OPUS_2026-09-22.md` (§1–14);
cómo funciona: `documentacion/SEMANTICA.md`.

**Falta una sola cosa para cerrar: el held-out nuevo del dueño** (≥ 95 %), que por la meta se pide ahora que
`semantic/` está migrado y la capa A pasa, y se corre una vez.

## Cifras

| Medida | Inicio (b5c9fe72) | Clase 1 | Ahora | Cómo |
|---|---:|---:|---:|---|
| Capa A — lo dicho de verdad a BAXY (768) | 96,0 % | 97,0 % | **98,3 %** | sólo-decisión, `semantic_corpus.py score` |
| · registro real de BAXY Definitivo (91) | 73,6 % | 82,4 % | **91,2 %** | ídem |
| · encuesta de 742 (676 abiertas/cubiertas) | 99,1 % | 99,1 % | 99,3 % | ídem |
| Capa B — ejemplos de los BAXY anteriores con forma de turno (20) | 50 % | 50 % | 55 % | ídem; §12 |
| Capa C — frases dichas a asistentes (muestra 1 000) | 54,4 % | 54,4 % | 55,7 % | ídem; oráculo ruidoso (abajo) |
| Guion del dueño 2026-09-21 (60) | 33 | 39 | **53** | producto, `semantic_replay.py conv` + revisiones |
| Held-out 2026-09-22, congelado (30) | 15 | 22 | **29** | ídem |
| 742 sólo-decisión | — | 0 distintas | 1 distinta (H0506, memoria que toma el shell) | `semantic_replay.py literals` |
| cien (población v18) | cien-98 100/0/100 | — | **cien-100 100/0/100** | conductor; lectura en `CIEN.md` |
| Full (`test_source_quality.ps1 -Mode Full`) | verde | — | **verde**: ruff, .NET 4 903, pytest 13 728 | |

Capas medidas sobre el corpus actual (filtro §12, etiquetas §14) para las cuatro columnas. Guiones medidos sobre
10dbcf34 (S8); los arreglos posteriores (destino «en YouTube mejor», lectura de cien-99) están probados con pruebas,
con la cien-100 y el Full, no con otra pasada de los guiones.

## Qué cambió en cómo entiende BAXY

Cada forma se arregló como forma y se probó con frases que el arreglo no nombra.

- **Hueco de diálogo** (clase 1): «20», «sí», «no, en YouTube», «apagalo», «averiguá qué dijeron» se re-arman con el
  turno anterior en un solo lector (mente), el shell ya no concatena. Rechazos, prohibiciones y el asentimiento a un
  pedido vacío no llenan el hueco; un dativo con su objeto dicho («devolvele el sonido») se entiende solo; el pronombre
  tras una pregunta pública («¿la nueva peli de X es buena?» → «investigala») es esa obra; un destino nuevo re-arma el
  último pedido por patrón.
- **Charla que no pide nada**: «me gusta crear cosas como tú», «odio estos fallos», «jajaja qué respuesta más rara» se
  contestan como charla (guarda del dueño 4/8 → 8/8; held-out 6/6), nunca si hay una orden o un pedido.
- **Misiones compuestas** con una parte que BAXY no hace: ofrece la posible con las palabras de la persona en vez de
  «no puedo abrir Steam ni…» (§13).
- **Buscar antes de afirmar**: opiniones de una obra pública y hechos con fecha van a la web.
- **Formas de enunciado**: orden después de charla, destino delante, deseo de escuchar, vocativos con los nombres de
  los BAXY anteriores (Gemma, Carter), voseo en reproducir y en el volumen, video/pantalla/brillo, lecturas que no se
  confirman («dime la hora exacta», «quién es X», «qué app está activa»).
- **Honestidad**: el veto de efecto inventado ya no confunde «caché» con «caché (yo)»; el código interno
  `request_analysis_failed` tiene su hecho y no se lee en voz alta.

## Estructura: `src/baxy_mind/semantic/`

`normalize` (fold único), `lexicon` (un sinónimo, un lugar), `grammar` (sobre del pedido, cabezas por forma),
`dialogue` (hueco), `guards` (entrada sin pedido), `reading` (**puerta `read()` → `Reading`**, formas de enunciado,
compuestas, charla), `patterns` (orquestador del patrón, antes `effect_intent`), `intent`, `catalog`, `temporal` y
trece dominios (`audio`, `display`, `windows`, `media`, `web`, `files`, `games`, `network`, `system`, `notes`,
`messaging`, `ui`, `apps`). `effect_intent` quedó en una capa de re-exportación mientras los llamadores migran; cada
traslado fue puro (0 diferencias en 4 946 lecturas del patrón). Herencia de los BAXY anteriores (ley 1) citada en
`documentacion/SEMANTICA.md`.

## Lo que no está y por qué

- **Guion del dueño, 7 turnos**: 22 (título de la ventana de PotPlayer: hay presencia, no lectura de título), 23–25
  (la búsqueda de «Colony» corre pero el redactor del informe rechaza y corta su borrador; después «investigala» queda
  sin tema), 38 y 42 (pulsar dentro de Steam: es el motor, Fase 4/5), 39 (recuperación tras dos fallos del modelo), 47
  (micrófono ya activo: el final dice «no fue posible cambiar su estado»).
- **Capa C**: la mayoría de sus fallos son del oráculo heredado (espera «conversación» para «silenciá el sonido», exige
  `office.document` para «open Word», un efecto para límites reales como generar imágenes). Sus re-etiquetas son
  públicas (RL1, RL2); los fallos reales encontrados en C se arreglaron como formas (volumen, video, pantalla, voseo).
- **Capa B** tiene 20 filas tras quitar notas técnicas que no eran turnos (§12); es poca población para concluir.

## Incidentes

- 2026-09-22: el held-out cerró VS Code dos veces («cerralo» + «sí, dale»). Arreglo en el hueco y ventana guardia en el
  harness.
- 2026-09-23 04:44: Windows Update reinició el PC a mitad de una réplica (no fue BAXY). Se completó con las filas que
  faltaban; antes de cada corrida larga se mira si hay un reinicio pendiente.
