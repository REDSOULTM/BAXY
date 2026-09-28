# COMPRENSION_NATURAL_2026-09-28 — Fase 3.5b «comprensión natural»: cierre

Rama `codex/kiro-goal-c03` (sin merge a `main`). Goal: `GOAL_COMPRENSION_NATURAL_v2_2026-09-28.md`. Estado por
mecanismo: `COMPRENSION_PROGRESO.md`; decisiones D1–D31: `DECISIONES_COMPRENSION_2026-09-25.md`; investigación:
`comprension-f1/INVESTIGACION_2026-09-27.md`. Producto al cierre: Qwen3.5-4B Q4_K_M + LoRA del decisor `full3`,
commit `d456f5a9` (M8–M41 que entraron, limpieza G1–G5, arreglo de la captura de la ventana activa).

**Veredicto: el goal no se cumple.** El FINAL, corrido una sola vez en la app real, queda en 74,3 % con la puntuación
automática y en 56,9 % con el revisor independiente, por debajo de la meta (85 %) y de la banda «parcial» (80–85 %)
del goal. Abajo, cada meta, la causa limitante medida y qué haría falta.

## 1. Resultado por meta

| meta | valor al cierre | meta | estado |
|---|---|---|---|
| FINAL total (app real, puntuación automática) | **74,3 %** (150/202) | ≥ 85 % | no |
| FINAL total (revisor independiente, calidad de lo publicado) | **56,9 %** (115/202) | ≥ 85 % | no |
| FINAL sueltos (automática / revisor) | 75,0 % / 55,9 % | ≥ 88 % | no |
| FINAL seguimientos (automática / revisor) | 71,9 % / 58,7 % | ≥ 80 % | no |
| inventados (revisor) | **1** (F-w12-t3: «el promedio es 3,14» sin dato) | 0 | no |
| ⚠ (turnos sin respuesta publicada) | **5,0 %** (10/202, `composition_failed`) | ≤ 1 % | no |
| guion del dueño | 51/60 (app real, M29; 24 y 25 no evaluables: la búsqueda web está bloqueada para esta red) | ≥ 53/60 | no |
| held-out | **29/30** (M29) | ≥ 29/30 | sí |
| cien | **98/100** (cien-108 en la app real con el producto del cierre; 96 con los 2 dudosos; 0 efectos de más). Fallan 073 «what is cache memory» (busca y dice «via web search») y 077 «still there?» (pregunta) | 100/100 | no |
| reserva MASSIVE (sólo decisión) | 86,4 % (82,2 % al empezar la fase) | ≥ 88 % | no |
| capa A | **96,4 %** | ≥ 96 % | sí |
| 742 | 19 decisiones distintas de la base, todas revisadas; hoy sólo cambió H0407, a mejor | sin cambios sin revisar | sí |
| Full | pytest 18 709 pasan; 1 falla: `test_detached_head_snapshot…` agota su tope de 45 s creando una worktree de 30 k ficheros (entorno, no código; en frío pasaba) | verde | casi |
| latencia visible p50 / p90 | 2,07 s / 4,88 s (FINAL en la app real) | ≤ 3 s / lo fácil ≤ 5 s | sí |
| VRAM de pico | 4 389 MiB de toda la GPU durante la medida, con ≈ 370–430 MiB de otros programas: BAXY ≈ 3 960–4 020 MiB | ≤ 4 096 MiB | al límite |

## 2. La causa limitante, medida

| capa | cifra | qué dice |
|---|---|---|
| decisor `full3` solo (sin lectores), DEV-B | 88,9 % sólo decisión | el techo del modelo en la decisión |
| producto, sólo la mente: DEV-B / DEV-C / FINAL | 80,2 % / 81,7 % / **81,2 %** | ≈ 81 % en conjuntos nuevos; los argumentos restan ≈ 4 puntos a la decisión |
| producto en la app real: DEV-A / FINAL | 80,8 % / **74,3 %** | la app resta ≈ 5–7 puntos: turnos que fallan al redactarse (3,5–5 %) y seguimientos cuya conversación vivida se aparta de la escrita |
| revisor independiente (calidad de lo publicado) | 56,9 % | además de la decisión: charla con errores de conocimiento o de cálculo del 4B, repreguntas de lo ya dado, límites mal dichos |

1. **El modelo.** Tras `full3` ninguna palanca mejoró el ciego: más SFT (`full4`, `full5`), few-shot dinámico, calibración
   de la decisión (CAL), tres rondas de preferencias (RPO), cuantización Q8 (D23–D30). R5 no encontró un modelo base
   que gane con claridad en español dentro de 4 GB (Gemma 4 E4B no cabe; LFM2.5 pide permiso de licencia).
2. **Los lectores y guardas** (prioridad del dueño del 28-09). El análisis por etapa mostró que en la reserva los
   lectores ganan al decisor solo (+91 el de efectos) y que en DEV-B la mayor pérdida eran respuestas correctas vetadas
   al redactar. Se estrecharon (M32, M33, M35, M36) y se confirmaron en DEV-C (246/301, 0 rotos), sin mover DEV-B.
3. **La app real.** Correr los conjuntos en la app (arnés nuevo `scripts/comprension_window.py`) destapó fallos que la
   medida de la mente no ve: redacciones vetadas (M37–M41), una confirmación pendiente que bloqueaba turnos y un
   bloqueo real de la app al capturar la ventana activa (arreglado, a7f528ec). Quedan fallos dispersos, uno por turno.

**Qué haría falta** (ninguno cabe en esta fase sin una decisión del dueño): un modelo base mejor en español dentro del
tope de VRAM, o subir el tope; datos de entrenamiento de conversaciones reales vividas en la app (no escritas); y
seguir cerrando fallos de redacción en la app real con un DEV nuevo en la ventana, no con conjuntos de la mente.

## 3. Qué cambió en BAXY en esta sesión (28-09) y entró

- **M32** junto a un contenedor de la colección propia, un género nombrado dice qué poner («play my rock playlist»).
- **M33** una redacción que nombra su idioma se responde en él («escríbeme un mensaje en inglés…»).
- **M35** lo que BAXY respondió a la persona no es un efecto; los números del pedido se dicen en una presentación.
- **M36** el acuse de una restricción no habla de BAXY en tercera persona.
- **M37** los días que faltan (para el finde, el viernes) y **M40** la hora dentro de un rato se calculan en código.
- **M38** la aclaración con causa interna se redacta como pregunta; **M39** nunca se pide un ID interno.
- **M41** la coletilla «en los resultados de búsqueda» se recorta en vez de vetar el informe.
- **Captura de la ventana activa** no tumba el núcleo y la app se recupera sola de una desconexión.
- **Ley 2**: −649 líneas (G1–G5: prompts huérfanos, restos de etapas retiradas, el índice E5 que nadie leía).
- **Medida**: DEV-C nuevo y sellado (301 turnos, doble etiquetado ciego); arnés de ventana oficial con ventana guardia
  que protege VS Code y devuelve volumen y brillo.
Lo anterior (M8–M31) y lo retirado, en `COMPRENSION_PROGRESO.md`.

## 4. Qué se probó y no entró (28-09)

M31 (líneas negativas del catálogo), CAL (D27), cuantización Q8, RPO rondas 2 y 3 (D28, D30), M34 (conversación
ajena: 3 roturas de `email.latest.reply`).

## 5. Pendiente y riesgos

- **cien-108**: 98/100 (`cien-108/adjudicacion.md`); 038 «if it didn't happen, say so» y 100 «post a letter to
  Eris» ya están bien; siguen mal 073 y 077.
- La búsqueda web está bloqueada para esta red (D22): los turnos de búsqueda del guion no se pueden evaluar.
- El FINAL ya se usó: una ronda nueva exige un conjunto nuevo sellado.
- Brillo del dueño: el primer ensayo lo puso en 100 sin guardar el valor previo (el arnés ya lo guarda).
- Fallos restantes a mirar: repreguntas por el ID de ventanas en órdenes de colocar dos ventanas (F-w06-t1), charla
  con errores de conocimiento del 4B, límites que niegan lo que el catálogo hace (F-s064), un dato inventado en una
  cuenta (F-w12-t3).

## 6. Cómo reproducir

- Conjuntos (fuera de git): `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\sets\` (FINAL `e05cf27e…d993`, DEV-C
  `7ffb35a3…f93a`). Mente: `scripts/comprension_eval.py run --decider-adapter …`.
- App real: `scripts/comprension_window.py turns` → `scripts/run_baxy_conductor.ps1` con `BAXY_MIND_TURN_AUDIT_PATH`,
  `BAXY_APP_TRACE` y `BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH` → `records` → `comprension_eval.py score` → `review`
  (ventana guardia y restauración de audio y brillo en el guion de la sesión, `scratchpad/cn/window_run.sh`).
- Revisión del FINAL: `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\window\final-once\REVIEW.reviewed.jsonl`.
