# Dataset v3 — fine-tuning con tool-results y replies grounded (2026-06-11)

## Por qué existe v3

Las alucinaciones cazadas en vivo (2026-06-10: "Es las 10:42 de la mañana." con
hora real 21:56; "Son las 20:47." en eval) tienen su RAÍZ en el formato de
entrenamiento v1/v2: cada ejemplo era `[user, assistant(tool_calls + reply)]`
**sin el turno de tool-result**, así que el modelo aprendió a responder DATOS
sin mirar ningún resultado. Encima, ~33 ejemplos traían horas concretas
fabricadas entrenadas verbatim y 642 templates se aplanaban a "Listo." (un
atractor: ~14% del dataset respondía igual).

## Qué entrena v3

    [user] -> assistant(tool_calls) -> tool_response(result real) -> reply

con el **invariante de grounding**: todo valor del reply existe en el result o
en el user_text. Dos direcciones de síntesis:

- **Familias de VALOR** (hora, fecha, batería, cpu/ram, procesos, volumen,
  ventanas, archivos): el valor se genera primero (RNG por fila, seed 42,
  reproducible) y el reply lo CITA.
- **Familias de CONTENIDO** (web, knowledge, vision, terminal, steam): el
  result se deriva del reply curado (payload := lo que el reply ideal afirma).

Más: ~5% de results `ok:false` con reply honesto (enseña a reportar fallos);
openers variados por idioma (anti-atractor); identidad Baxy (66 restos de
Carter/"Gemma 4"-asistente corregidos); args extraídos del user_text solo con
alta precisión; actions clampeadas a los enums REALES de los schemas.

## Detalles técnicos críticos (no perder)

1. **Render**: el `chat_template.jinja` del modelo mete tool_call +
   tool_response + reply en UN solo turno `<|turn>model`. Los mensajes
   `role:"tool"` con `tool_call_id` se renderizan como bloques nativos
   `<|tool_response>response:NAME{value:<|"|>...<|"|>}<tool_response|>` —
   bit-idéntico al re-feed del runtime (verificado por render directo).
2. **MÁSCARA DE LOSS** (lo más importante): `train_on_responses_only` deja
   loss sobre TODO el turno model — incluido el tool_response inyectado. Sin
   máscara extra, el FT enseñaría a GENERAR resultados (alucinarlos tras el
   tool-call). `mask_v3.mask_tool_response_spans` pone labels=-100 en los
   spans `[<|tool_response>(id 50) .. <tool_response|>(id 51)]` inclusive,
   vectorizado. Testeado en `_test_mask_v3.py` (sintético + fila real
   tokenizada: result enmascarado, tool_call y reply CON loss).
3. **Longitudes**: p50=100, p99=238, máx 583 tokens — sin riesgo de truncado
   con MAX_SEQ=2048.
4. **Epochs default 2** (rollback v1 midió que 3 sobreajustan el E2B).
5. Shapes de result calcados de ejecuciones REALES (`out/_readonly_shapes.json`
   capturado con el ToolRegistry real; `out/_real_result_samples.json` minado
   de traces de producción excluyendo `_eval_mock` — el mock inventa cifras).

## Pipeline (en dataset_finetune/, gitignored — esta es la receta)

    cd dataset_finetune/scripts
    python build_v3.py              # train.jsonl -> train_v3.jsonl (6656 filas)
    python validate_v3.py           # 7 gates; exit 1 si falla alguno
    python _test_mask_v3.py         # máscara tool_response
    # con .venv de Unsloth (py3.12) y GPU LIBRE:
    python train_ft.py --smoke      # 200 ej, valida pipeline + VRAM
    python train_ft.py              # full (usa train_v3.jsonl automáticamente)

## Iteración 2 (mismo día): auditoría semántica estilo APIGen + papers

La verificación semántica muestral (etapa 3 de APIGen, arXiv:2406.18518) sobre
la primera build cazó 8 clases de incoherencias en la SÍNTESIS — todas
arregladas y re-validadas:

1. Guesses por-default que recreaban el atractor ("activa el modo avión" →
   system(time) → "Son las 12:24."). REGLA DE ORO nueva: nunca sintetizar un
   reply de valor desde un guess por-default; sin señal clara → result genérico
   + reply curado.
2. Acciones equivocadas ("cerrá la ventana de X"/"borra la carpeta" caían a
   `list` con reply non-sequitur) → guesses multilingües por familia con
   close/min/max ANTES de list, y filesystem delete/read/mkdir/search.
3. Preguntas respondidas con ack ("¿qué alarmas tengo?" → "Hecho.") → 95 filas
   DROPPED (calidad > cantidad, LIMA) + gate G8 que lo impide a futuro.
4. "está instalado X" caía a open ("abrí X" = mentira) → familia search +
   reply instalado/no-instalado grounded en matches.
5. Nombres multi-palabra rotos ("Visual" por "Visual Studio Code") → extracción
   de capitalizados consecutivos.
6. Replies de valor pisando filas multi-tool → kind='value' explícito.
7. Volumen sin número inventaba un nivel → solo con número extraído.
8. media play ahora incluye ~25% estado ATTEMPTED real (Spotify no auto-play)
   con reply honesto "abrí la búsqueda; tocá el primer resultado" — el
   overclaim residual medido en vivo 2026-06-11.

Augmentations (ToolMind arXiv:2511.15718 / FunReason-MT arXiv:2510.24645:
multi-turno + clarificación; el bug en vivo: artista-sin-título):
- 48 filas artista-sin-título 6 idiomas (query=ARTISTA, mitad attempted).
- 54 filas DOS-TURNOS con history (pedido ambiguo → el asistente pregunta →
  el user completa → tool con args correctos).
- 12 filas de clarificación pura (preguntar, NO adivinar ni llamar tool).
- Dedup exacto (17) y drop pregunta+ack (95): 6656 → 6658 filas netas.

## Gates (estado: TODOS PASS sobre train_v3.jsonl, 6658 filas)

| Gate | Qué mide | Estado |
|------|----------|--------|
| G1 grounding | 0 cifras/horas del reply sin sustento en result∪user_text | PASS |
| G2 identidad | 0 Carter / "Soy Gemma 4" como asistente | PASS |
| G3 anti-atractor | ningún reply idéntico >80 veces (antes: 924 "Listo.") | PASS |
| G4 vocabulario | tools y actions existen en los schemas reales | PASS |
| G5 balance | peso efectivo es = 57.6% (rango 52-62) | PASS |
| G6 render | muestra renderiza por el jinja real, bloques = results | PASS |
| G7 no-vacíos | 0 final_reply vacíos | PASS |
| G8 pregunta+ack | 0 preguntas respondidas con "Hecho."/"Listo." | PASS |
| G9 estados honestos | ≥30 attempted (39) y ≥30 ok:false (33) | PASS |
| G10 trayectorias | ≥50 multi-turno (54) y ≥10 clarificaciones (388) | PASS |

Longitudes finales: p50=93, p99=219, máx 551 tokens (MAX_SEQ 2048, 0 truncados).

## Criterios de papers cubiertos (fuentes)

- APIGen (arXiv:2406.18518): verificación format ✓(G4/G6) + execution-shape
  ✓(shapes calcados de ejecuciones reales) + semántica ✓(auditoría muestral
  estratificada, 2 rondas; G1/G8 automatizan los hallazgos).
- ToolMind (arXiv:2511.15718) / FunReason-MT (arXiv:2510.24645): multi-turno,
  clarificaciones, trayectorias con estado ✓(G10); diversidad de dominios
  ✓(67 tools, 22 categorías).
- "Failure Makes the Agent Stronger" (arXiv:2509.18847): resultados de fallo
  con reporte honesto ✓(G9, 33 ok:false + 39 attempted).
- Language confusion (EMNLP 2024, ya en docs del repo): balance es 57.6%
  efectivo + replies SIEMPRE en el idioma de la fila ✓(G5 + tablas por idioma).
- LIMA (calidad>cantidad): drop de filas que enseñaban a no-responder ✓.

## Presupuesto del retrain (medido en corridas previas, 4060 Ti 16GB)

- Training QLoRA: 32-63 min (5664 ej) → estimado **~50-80 min** (6656 ej, 2
  epochs, filas ~30% más largas). VRAM peak **~15.5 GB** → la GPU queda
  inutilizable para otra cosa durante el run.
- Merge bf16 + GGUF Q4_K_M + imatrix: ~20-25 min.
- Evals post-FT (gate 0% tools inventadas + dimensiones + en vivo): ~30-60 min.
- **Total: ~2-2.5 h de GPU dedicada.** Si falla a mitad: el LoRA queda en
  out/checkpoints (reanudable); el modelo prod NO se toca hasta el swap final.

## Gates de ACEPTACIÓN post-entrenamiento (definidos ANTES de entrenar)

1. 0% tools inventadas con array de tools (igual que v2 — NUNCA medir sin array).
2. Cero replies con hora/cifra no presente en el tool_result en un eval de 50
   prompts de hora/batería/RAM en vivo (el bug raíz, ahora medible).
3. Español coherente: eval multilingüe sin degradar es (lección rollback v1);
   ningún idioma cae >2 puntos vs baseline.
4. Identidad: "quién eres" → Baxy en 6/6 idiomas.
5. Routing intacto: suite de routing y los 2 keypress pre-existentes iguales.

## Pendiente / decisiones para v4

- prev_text casi no se usa (8 filas): falta multi-turno con historia.
- Encadenamientos multi-tool (251 filas) llevan results genéricos por paso.
- Considerar ejemplos con tool_response de ERROR + reintento (error recovery).
