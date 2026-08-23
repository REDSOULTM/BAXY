# Goal 08 — la primera señal

**Cerrado el 2026-08-23.** Nunca hay silencio muerto: si el camino va a tardar,
BAXY dice que entendió y está en ello; si va a tardar poco, calla y responde.

> **El estado en una línea:** primera señal GPU p50 **0,009–0,011 s** y p95
> **0,146–0,161 s** (dos corridas, 17 turnos con camino por modelo). CPU p50
> **0,026 s**, p95 **0,683 s**, máx **2,973 s**. Acción simple completa y
> verificada p50 **0,12 s**. Tres ceros 0/0/0. Exactitud **111/124**.

## 1. Herencia

| Qué | Dónde |
|---|---|
| R102 | primera señal p95 2,668 s; el fallo es el camino por modelo |
| R132 | streaming techo 0,33 s, insuficiente; acuse de plantilla prohibido |
| R133 | la decisión primaria bloquea la señal; 2–5 llamadas, pegamento ≈ 0 |
| R134 | recortar shortlist a ojo puede tirar la hoja correcta |
| Goal 06 | Field publicaba etapa sin `label`; acting «Sigo.» / «Still working.» |

No se reabrió streaming. No se recortó el shortlist. No se cambió el GGUF.

## 2. Qué se cambió

Tres funciones, sin orquestador nuevo:

- **Estima.** Camino del reconocedor / conversación cerrada ≈ 0,07–0,9 s → calla.
  Camino por modelo ≈ 2,5 s, o más de un paso → avisa.
- **Formula.** Prosa de este pedido (`Sigo con …` / `Still working on …`), no
  «un momento…». Nunca afirma un resultado. La guarda de acting del goal 06
  la acepta.
- **Corrige.** Si la verificación desmiente, la persona lee la corrección
  (`HonestyCorrection` + `visible_after_verification`).

El sidecar emite `turn.signal` **antes** de `decide_turn` y **antes** de las
sondas de identidad. El shell lo pone en `FieldProgressNotice.Label`. Un hito
se formula a los **3,01 s** sin salida visible (`MilestoneDue`), no al
siguiente pulso de 4 s. El pulso de etapa es 1 s; no sustituye al due.

## 3. Números

Población: las 17 peticiones de `measure_first_signal_latency.py` (incluye
chiste, fotosíntesis, fuera de catálogo, CPU load). Dos corridas GPU
consecutivas, árbol congelado.

| Reloj | Corrida 1 | Corrida 2 | Barra |
|---|---|---|---|
| Primera señal GPU p50 | 0,011 s | 0,009 s | ≤ 1,0 s |
| Primera señal GPU p95 | 0,146 s | 0,161 s | ≤ 2,0 s |
| GPU máx | 0,480 s | 0,551 s | 3 s silencio |
| Turnos sin señal | 0 | 0 | 0 |
| CPU p50 / p95 / máx | 0,026 / 0,683 / 2,973 s | — | silencio ≤ 3 s |
| Acción simple verificada p50 | 0,120 / 0,119 s | ≤ 2,5 s | |

Los reconocidos no emiten acuse (0,003–0,06 s hasta el resultado). Los del
modelo emiten prosa a ~0,01 s. Evidencia:
`artifacts/product/first_signal_latency.json`,
`first_signal_latency_cpu.json`,
`simple_complete_latency.json`.

## 4. Llamadas por modelo que siguen

Descomposición sobre 8 turnos difíciles
(`artifacts/development/turn_call_decomposition_goal08.json`): **5 a 8**
llamadas por turno, p50 de pared **2,53 s**. Eso es el turno **completo**, no
la primera señal.

| Llamada | Nº | Mediana | Por qué sigue |
|---|---|---|---|
| `turn_policy` | 7 | 0,86 s | decide conversation / action / clarify / plan |
| `operation_identity` | 24 | 0,18 s | no negar una capacidad que el catálogo tiene (03B) |
| `conversation_reply` | 7 | 0,63 s | la respuesta que la persona lee |
| `semantic_effect_guard` | 7 | 0,32 s | no inventar un efecto |
| `response_language` | 7 | 0,11 s | idioma del pedido |
| `final_writers` | 2 | 0,22 s | corrección de prosa |
| `single_effect_selector` / `effect_count_verifier` / `operation_compatibility` | 1 cada | 0,28–0,43 s | sólo cuando el turno las pide |

No se recortó ninguna: el dueño eligió quitarse sobrecarga, y estas no son
capas apiladas — cada una tiene un invariante medido. Recortar
`operation_identity` reabre «no puedo X» sobre algo que sí hace.

## 5. Exactitud y tres ceros

Misma población del goal 03 (`761c1bc3…`, 160 filas). Una corrida.

| | Valor | Último publicado |
|---|---|---|
| Efectos no pedidos | **0** | 0 |
| Éxitos no verificados | **0** | 0 |
| Respuestas fijas | **0** | 0 |
| Conversaciones/aclaraciones vacías | **0** | 0 |
| Exactitud in-catálogo | **111/124 = 89,5 %** | 03C mediana 114/124 = 91,9 % |

La diferencia de tres filas está en el ruido ±3 que el goal 03 midió sobre
124. Fuera de catálogo: 36/36 abstenciones honestas. Scorer de honestidad
congelado, mismos SHA que el goal 04.

## 6. Criterios

- [x] Números con población difícil y CPU aparte
- [x] Ninguna tarea pasa 3 s en silencio (GPU máx 0,55 s; CPU máx 2,97 s)
- [x] Señal temprana condicional y formulada
- [x] No afirma resultado; autocorrección en `honesty_self_correction`
- [x] Llamadas restantes publicadas
- [x] Sin regresión de tres ceros; exactitud dentro del ruido del corpus
- [x] Publicado en `origin/main`
