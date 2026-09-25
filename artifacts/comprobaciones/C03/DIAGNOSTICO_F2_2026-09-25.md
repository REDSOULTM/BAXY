# F2 — Diagnóstico por camino y modelo libre (2026-09-25)

Goal: `PROMPT_OPUS_COMPRENSION_NATURAL_2026-09-25.md` §F2. Sólo decisión, sin efectos, HEAD de partida (`src` =
b34c3f39). DEV-A se mira; DEV-B sólo por su cifra. Arneses: `scripts/comprension_eval.py` (producto) y
`comprension-f1/free_model.py` (modelo libre: la conversación tal cual, catálogo compacto por familia, reglas del
dueño, salida JSON restringida por esquema; ningún lector, hueco de diálogo, lista corta ni veto delante; el mismo
`llama-server` b9980, 1 slot, 12 288 de contexto). Cifras de decisión (`verdict[0]`): el arnés libre aún no extrae
argumentos, así que la cifra estricta lo penaliza sin motivo.

## Quién decide hoy y cuánto acierta (producto, DEV-A, 260)

| camino | turnos | acierto |
|---|---|---|
| selector del modelo + compuertas | 158 | 55 % |
| lector de efectos | 42 | 74 % |
| lector de conversación | 31 | 87 % |
| aclaración por lector | 11 | 64 % |
| recuperación total (el turno falló dos veces) | 18 | 17 % |

Causas de los 105 errores (referencia: Qwen3.5-4B libre):

| causa | errores |
|---|---|
| el selector falla y el modelo libre acierta | 20 |
| selector y modelo libre fallan | 31 |
| **un veto tumba una elección cruda correcta** (domain_grounding 9, action_grounding 3, conversation_effect_shape 3, closed_refusal_withdrawn 3, otros 2) | 20 |
| **validadores de redacción tiran el turno a recuperación** (`shaped_presentation` 14, `compound_conservation` 12, idioma 2, truncado 2, ancla de límite 2; intentos) | 15 |
| un lector se adelanta mal y el libre acierta | 4 |
| un lector falla y el libre también | 15 |

Hueco de diálogo en los 68 seguimientos de DEV-A: sin re-armar 21/40, re-armado por modelo 7/14, propuesta del modelo
rechazada 3/9, por patrón 2/2.

## Modelo libre (sólo decisión)

| configuración | DEV-A (260) | seguim. A (68) | DEV-B (253) | seguim. B (66) | p50 | VRAM pico servidor |
|---|---|---|---|---|---|---|
| **producto (base)** | 159 (61,2 %) | 38 | 182 (71,9 %) | 40 | 1,97 s | ~3,5 GB (3 slots × 4 k) |
| Qwen3-4B-2507 libre | 116 (44,6 %) | 34 | — | — | 0,27 s | 3 514 MiB |
| Qwen3-4B-2507 libre, pedido reescrito primero | 139 (53,5 %) | 30 | — | — | 0,58 s | 3 514 MiB |
| Qwen3.8-4B-Distill Q4 libre | 164 (63,1 %) | 42 | 180 (71,1 %) | 49 | 0,59 s | 3 144 MiB |
| Qwen3.8-4B-Distill Q4, pedido reescrito | 170 (65,4 %) | 44 | — | — | 0,88 s | 3 144 MiB |
| Qwen3.8-4B-Distill Q5 libre | 158 (60,8 %) | 44 | — | — | 0,61 s | 3 504 MiB |
| **Qwen3.5-4B Q4 libre** | **182 (70,0 %)** | **46** | **196 (77,5 %)** | **56** | **0,36 s** | **3 104 MiB** |

Lectura:
- El modelo **actual** suelto decide peor que la tubería (44,6 %): la tubería le suma ~17 puntos. Por eso el paso 6
  vio resultados idénticos entre modelos: los fija la tubería.
- **Qwen3.5-4B libre supera a la tubería entera en los dos conjuntos** (+8,8 puntos en A, +5,6 en B) y sobre todo en
  seguimientos (+8 y +16 turnos: 84,8 % en DEV-B), con un quinto de la latencia de decisión y menos VRAM. La ley 1
  lo había rechazado **dentro** de la tubería (Goal 03B: 58/124 punta a punta; R80 por VRAM con 3 slots); aquí se
  mide otra cosa: el modelo con la conversación delante y sin compuertas.
- La destilación de Qwen3.8 (pedido del dueño) no mejora a su base Qwen3.5-4B en decisión (164 frente a 182 en A).
- Donde el producto sigue ganando: **sueltos de DEV-B** (97 frente a 88 de 125). Los fallos del modelo libre en A
  son de política y de datos, no de contexto: descripciones del catálogo técnicas («sesión SMTC») que confunden
  pausar/siguiente, volumen absoluto/relativo y abrir app/reproducir; preguntas de más en pedidos completos y en
  seguimientos públicos; límites contestados como charla; dato personal que falta decidido como acción.

## Reparto simulado (lectores que deciden bien + modelo libre para el resto)

| | DEV-A | DEV-B |
|---|---|---|
| Qwen3.5 libre solo | 182 | 196 |
| + lector de conversación | 182 | 196 |
| + lectores de conversación y efectos | 187 | 193 |
| + … y aclaración explícita | 189 | 194 |

Con Qwen3.5 los lectores delante ya no suman en DEV-B: la decisión la puede llevar el modelo con contexto; las
reglas quedan para lo sensible y para lo que el modelo mide peor.

## Qué decide el diseño de F3/F4

1. Configuración ganadora de F2: **decisor de modelo con la conversación completa y el catálogo entero**, sin lista
   corta ni vetos que tumben su elección; lectores sólo donde midan mejor (a decidir en F4 con DEV-B).
2. F3: torneo en esa configuración (Qwen3.5-4B, Qwen3-4B, Qwen3.8-Distill, Granite 4.2, Gemma 4 E2B refrescado,
   Phi-4-mini, Qwen3-8B IQ3), con la regla prerregistrada.
3. F4, por orden de peso medido: (a) el decisor nuevo sustituye selector + compuertas + recuperación en el camino del
   modelo (retira vetos: 20 errores; validadores que tiran el turno: 15); (b) catálogo del decisor en lenguaje de
   usuario (dato, no regla); (c) argumentos desde el pedido reescrito por el mismo decisor.
