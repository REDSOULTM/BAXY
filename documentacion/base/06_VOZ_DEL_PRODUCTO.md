# Goal 06 — la voz del producto

**Cerrado el 2026-08-23.** Todo lo que la persona lee lo formula el modelo.

> **El estado en una línea:** los 255 literales fijos del censo r0 son ahora
> hechos JSON que entran a `message.compose`; la cola sólo publica prosa
> validada. El carácter vive en `USER_MESSAGE_PROMPT`.

## 1. Herencia

| Qué | Dónde |
|---|---|
| Censo r0 | `artifacts/development/goal06_censo_voz_r0.json` — 255 literales / 21 ficheros |
| Cola `message.compose` | `PendingModelMessageQueue` + `ModelMessageComposer` — se copió, no se inventó otra ruta |
| FunctionGemma Q2 | `biblioteca/functiongemma/raiz/README_SPEECH_MODEL.md` — Q2 inventaba «fysico»/«lumínar»; persona por prompt en Q4. Pista, no conclusión: el decisor de hoy es Qwen3-4B-Q4_K_M |

## 2. Rutas que publicaban constante (y qué se hizo)

| Superficie | Antes | Ahora |
|---|---|---|
| `ProductOperationNarrator` (123) | `switch` de frases | `OperationVisibleFacts.FromOutcome` |
| `MainWindowViewModel` (54) | «No pude…» / «Estoy lista…» | `TurnVisibleFacts.*` |
| Progreso Field (`FieldBridgeContract`) | «Estoy entendiendo tu petición.» | etapa sin label (señal no verbal) |
| Misión / privada / proyección | plantillas | hechos JSON |
| `narrate` | prompt paralelo | `compose_user_message` |
| Degradado compose | «Un momento, estoy preparando…» | espera en silencio; la cola reintenta |

El censo `scripts/censo_voz_visible.py` queda en **0 literales / 0 ficheros**. `llm.py` sigue excluido: ahí vive el carácter.

## 3. Registro (editable)

En `USER_MESSAGE_PROMPT` / `SYSTEM_PROMPT` / `CPU_USER_MESSAGE_PROMPT`:

- compañero, un él, tutea
- una frase
- «Listo, Spotify está abierto y sonando»
- «No pude: Spotify no responde»
- «eso no lo hago»
- idioma del pedido
- sin fine-tuning

## 4. Palabras inventadas

La guarda `visible_reply_invents_a_spanish_infinitive` sigue en el compose enviado. No se subió de cuantización: el modelo de hoy ya es Q4_K_M; no hay un GGUF más ligero del mismo modelo en disco; Q2 de Gemma 4 se rechazó por degeneración medida en 2026-06 y no se reabre sin un candidato presente.

## 5. Auditoría de cien respuestas (2026-08-23)

Corrida: `py -3.12 scripts/goal06_voice_sample.py artifacts/development` sobre
Qwen3-4B-Q4_K_M, sidecar real, `type=message.compose.result`. Evidencia:
`artifacts/development/goal06_cien_respuestas.jsonl` y
`artifacts/development/goal06_prosa_ab.json`. n=100, bad=0 del scorer, p50 0,22 s.

Leídas a mano las 100 de ese JSONL. Polaridad y causa coinciden; 0 copias de
Spotify ajeno; 0 códigos; 0 inventadas del conjunto cerrado (incluida «Abrbió»);
0 stalls; 0 JSON; 0 «Listo,» en fallo, welcome o acting.

| Tipo | Lo que sale |
|---|---|
| Welcome | «Hola.» / «Hi.» / «Hi there.» — masculino, una frase, sin apps |
| Aclaración | «¿Qué quieres abrir?» / «What do you want to open?» / «What do you want to close?» |
| Misión | «Listo, Abrí Steam y puse el volumen en 40 %.» y «Listo, Abrí Word y creé la nota «Borrador».» — los dos pasos |
| Género | «Listo, Calculadora está abierta.» / «Listo, Terminal está abierta.» |
| Mayúsculas | «Listo, el volumen está en 80.» / «The volume is 25.» / «¿Qué quieres cerrar?» |
| Open EN | «Word is open.» / «Calculator is open.» |
| Open ES | «Listo, Word está abierto.» |
| Nota | «Listo, la nota Ideas está creada.» |

Registro cuando el hecho es rico: «Spotify está abierto y sonando»; «Spotify is open and playing»; «No pude: se agotó el tiempo»; «I couldn't: it didn't respond»; «eso no lo hago»; «El audio ya no está silenciado».

Queda «no la encontré» con apps masculinas (Steam/Chrome): es la causa en prosa, no un hueco de otro nombre. Anotado.

## 6. Criterios

- [x] Cero constantes en el censo de prosa publicable
- [x] Personalidad en el prompt
- [x] Accesibilidad / narrate por la misma ruta
- [x] Guarda de infinitivos inventados en compose
- [x] Cien respuestas leídas a mano (`artifacts/development/goal06_cien_respuestas.jsonl`)
- [x] Publicado en `origin/main`
