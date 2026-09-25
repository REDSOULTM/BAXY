# Paso 6 — experimento de modelo acotado (2026-09-25)

Paso 6 de [`PROPUESTA_METODO_COMPRENSION_2026-09-25.md`](PROPUESTA_METODO_COMPRENSION_2026-09-25.md), ley 4
(lo más ligero que cumpla; 4 GB de VRAM es el techo). Sólo decisión, sin efectos. Esta nota fija el método y la
regla de decisión **antes** de medir; la cifra la pone la corrida de la raíz. No cambia `src/`.

## Qué se compara

| modelo | GGUF (Q4_K_M) | bytes | SHA-256 | licencia |
|---|---|---|---|---|
| Qwen3-4B-Instruct-2507 (actual) | `unsloth/Qwen3-4B-Instruct-2507-GGUF@a06e946b` | 2 497 281 120 | `3605803b…c67e597` | apache-2.0 |
| Qwen3.5-4B | `unsloth/Qwen3.5-4B-GGUF@e87f1764` (Qwen no publica GGUF oficial; es la última revisión) | 2 740 937 888 | `00fe7986…ef11a4` | apache-2.0 |
| xLAM-2-3b-fc-r | `Salesforce/xLAM-2-3b-fc-r-gguf@a40e82c2` (oficial) | 1 929 902 656 | `bd1a0480…e47ae43` | **cc-by-nc-4.0** |

Todo en `D:\BAXYRuntime\experiments\models\` (xLAM en `xlam-2-3b-fc-r-a40e82c2\`, descargado con un `HF_HOME`
aislado; Qwen3.5 ya estaba en `qwen35-4b-e87f1764\` y su SHA coincide con el registrado en R80). Servidor:
llama.cpp b9980 (`38a9d28e…`), con los flags del producto (`LlmRuntime._server_command`: `-ngl 99`, 3 slots, KV q8,
`--jinja`, `--reasoning off`).

Plantillas: Qwen3 y Qwen3.5 usan la embebida (la de Qwen3.5 exige un solo mensaje de sistema; `_post` ya los une).
La embebida de xLAM-2 **no** sirve para las tool calls de b9980: con mensaje de sistema omite su instrucción de
formato y el modelo responde un arreglo JSON en `content` (V58: cero llamadas o HTTP 500). Se mide como
`xlam-hermes`: la plantilla `<tool_call>` de su base Qwen2.5, byte a byte la embebida en el GGUF de
Qwen3-4B-Instruct-2507, pasada con `--chat-template-file`. `xlam-native` (la embebida) queda disponible para
confirmar V58. Licencia: cc-by-nc-4.0 prohíbe el uso comercial; aunque ganara, no se promueve sin decisión del dueño.

## Lo heredado (ley 1)

- Qwen3.5-4B ya se midió y rechazó: R80 (2026-08-11, 11 errores semánticos en GPU, pico 3 077,6 MiB sobre 3 072),
  Goal 03B (58/124 con las puertas, p50 4,4 s) y el híbrido DeltaNet pierde la reutilización de prompt
  (llama.cpp #21831), que es el camino caliente del selector.
- xLAM-2-3b: V59 lo rechazó antes del real (180/477 positivos en sintético, 278 filas con esquema inconsistente).
- Se vuelve a medir porque la población es otra: los seguimientos de conversación, donde la propuesta ve el techo
  multi-turn del modelo actual (BFCL).

## Población y oro

Las tandas 1–6 son mensajes sueltos (sin conversación): los turnos de conversación de las tandas 1–7 son los de la
tanda 7, **42 turnos, 32 seguimientos**: las 4 conversaciones escritas de `tanda-07m` (con `expect`) y las 6
públicas de `tanda-07c` (oasst2 es, SGD en). El conjunto es privado (no entra en git).

- Historia fija e igual para los tres modelos: en las públicas, el turno del asistente de la propia fuente (SGD,
  oasst2); en las escritas, una respuesta coherente con el `expect` del turno anterior (ese turno salió bien). Si el
  turno anterior fue una pregunta que pide un dato, viaja como `pendingObjective`, como lo manda la App.
- Oro de decisión por turno: el conjunto de decisiones aceptadas (operación exacta del catálogo, `clarify`,
  conversación, límite). Sale del `expect` en las escritas y, en las públicas, de las reglas del dueño (lo público
  se busca, un pedido completo no se repregunta, un límite se dice llano). La revisión de la primera pasada de la
  tanda 7 (fila 7 de `USO_REAL_2026-09-23.md`, §1 de la propuesta) marca como fallo los mismos turnos.
- Oro de reescritura (sólo seguimientos): o el mensaje ya se entiende solo / es charla (se conserva: solape de
  palabras ≥ 0,8), o grupos de palabras que el pedido autónomo debe llevar (el lugar, el tema, la cantidad).
  Suelo: no reescribir nada acierta 13/32.

## Qué hace el arnés

Por modelo: la mente del producto (`python -m baxy_mind` del checkout) arranca su llama-server; cada turno pasa por
`turn.decide` (lectores, selección nativa con los prompts y candidatos del catálogo, vetos) sin ejecutar nada.
Después, contra el mismo servidor: la reescritura del producto (`rewrite_in_context`) forzada en los 32
seguimientos y juzgada por su guardia (`rewrite_stays_in_context`; lo que la guardia rechaza cuenta como el mensaje
original), y un humo de dos pedidos que dice si la plantilla trae tool calls. Registra por turno la decisión, el
camino (`decision_path`: lector o modelo), el re-armado del slot de diálogo, el tiempo de pared y, por llamada al
modelo, `prompt_ms`/`predicted_ms`/`cache_n` (auditoría opcional del producto); pico de VRAM atribuible
(contador GPU Process Memory del proceso y su árbol), RAM (RSS del árbol) y `nvidia-smi` total. Exige que no haya
ningún llama-server al empezar, los detiene todos en `finally` y sale con error si queda alguno.

## Regla de decisión (prerregistrada)

Un candidato mejora sólo si: **+4 turnos** en seguimientos bien decididos **o** en reescrituras efectivas, sin
perder más de 1 en la otra métrica ni en los 42 turnos; p50 de decisión y p50 del selector por turno ≤ 1,25× el
actual; pico de VRAM del llama-server ≤ 4 096 MiB (se informa también contra los 3 072 de R80). Se informa el
McNemar exacto de los discordantes (con 32 ítems, +4 no es significativo por sí solo). Si ninguno cumple:
**se sigue con Qwen3-4B** y queda escrito aquí. Si uno cumple, eso no lo promueve: faltan las 742, Full, una tanda
ciega y, para xLAM, el dueño.

## Cómo correrlo (raíz, GPU libre, BAXY cerrado)

Arnés en el scratchpad de la sesión, `…\scratchpad\model6\` (`compare.py`, `mind_entry.py`, `items.jsonl`,
`build_items.py`, `xlam-hermes.jinja`); se validó con `--dry-run` y con una prueba de fontanería sin GPU
(`selftest_fake.py`: servidor OpenAI y mente falsos).

```powershell
$py = "$env:LOCALAPPDATA\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe"
& $py -X utf8 <scratchpad>\model6\compare.py --repo "<checkout a medir>"   # añade --models ...,xlam-native para confirmar V58
```

Salida: `model6\run-<fecha>\summary.md` (tabla y veredicto) y, por modelo, decisiones, reescrituras, auditorías y
`meta.json`. Tiempo esperado: 5–8 min por modelo (hash de los GGUF, carga, índice de evidencia, 42 decisiones, 32
reescrituras), 15–25 min los tres.

## Resultado

Pendiente de la corrida de la raíz.

## Resultado (corrida 2026-09-25 01:53, `integ/uso-real` @ 9ccfafd3, 42 turnos de conversación de la tanda 7, 32 seguimientos)

| métrica | Qwen3-4B (actual) | Qwen3.5-4B | xLAM-2-3b (hermes) |
|---|---|---|---|
| decisiones correctas en seguimientos (32) | 23 | 23 | 23 |
| decisiones correctas (42) | 33 | 33 | 33 |
| reescrituras efectivas correctas (32) | 21 | 22 | 15 |
| decisión p50 / p90 | 1,82 / 3,09 s | 2,65 / 5,42 s | 1,48 / 3,03 s |
| VRAM pico llama-server | 3 488 MiB | 3 166 MiB | 2 238 MiB |
| licencia | apache-2.0 | apache-2.0 | cc-by-nc-4.0 |

Qwen3.5-4B: +0 decisiones (McNemar exacto p = 1,0), +1 reescritura, más lento. xLAM-2-3b: +0 decisiones, −6
reescrituras, más rápido, licencia no comercial. **Veredicto: se sigue con Qwen3-4B-Instruct-2507**; ningún candidato
mejora con el margen prerregistrado. La comprensión se sube con el método (estado del diálogo, reescritura, datos).
