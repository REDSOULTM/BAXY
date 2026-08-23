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
`artifacts/development/goal06_prosa_ab.json`. n=100, scorer bad=0, p50 0,22 s.

Compose no recibe ni reintenta la frase publicada. Tercer intento si hace falta,
aún sobre hechos JSON. Causas sin género. `effect=closed` sólo en éxitos.
Acting no ve el prompt con «estado observable»; el fallo de misión no recibe
los pasos hechos.

Leídas a mano las 100. Cero vacíos. Cero palabras inventadas. Cero «estado
observable». Cero «I opened Word» en mission-fail. Timeout/close/mute/open-en-
Terminal hablan: «No pude: el tiempo para esperar se agotó.» / «The window is
closed.» / «Listo, el volumen está mutado.» / «Terminal is open.» / «Steam está
cerrado.» Inglés de open nombra la app. Acting: «Sigo adelante.» / «Still
working on the issue.» (no afirma el resultado). Mission-fail-en: «I couldn't:
mission unfinished.» Notas: «Nota: Ideas» / «Listo, el título es "Alfa" y hay
una nota.»

Quedan notas dichas «abiertas», unmute telegráfico («Unmuted.») y horas
sueltas. Anotado.

## 6. Criterios

- [x] Cero constantes en el censo de prosa publicable
- [x] Personalidad en el prompt
- [x] Accesibilidad / narrate por la misma ruta
- [x] Guarda de infinitivos inventados en compose
- [x] Cien respuestas leídas a mano (`artifacts/development/goal06_cien_respuestas.jsonl`)
- [x] Publicado en `origin/main`
