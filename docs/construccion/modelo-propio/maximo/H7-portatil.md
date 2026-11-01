# H7 en el notebook: de dónde sale la lentitud tras una herramienta

Fase 3 («al 100 %»). La meta es −0,4 s o más en la p50 de la primera respuesta, en la misma máquina. Primero
se desglosó la e2e del holdout v5 del notebook (semilla 1, mismos casos para `inicio` 86991ca9d, `maximo`
452854a18 y `final` 19be8b42a): etapas del App (`app-trace.jsonl`, `events.jsonl`) y peticiones de la mente
(`mente/turns.jsonl`; sólo `final` tiene la traza de la mente en su corrida).

## 1. El +0,9 s es el aviso

| | `inicio` | `maximo` | `final` |
|---|---|---|---|
| p50 de la primera respuesta, todos los turnos | 3 473 ms | 4 316 ms | 4 318 ms |
| La respuesta esperó al fin del aviso | 0 de 60 | 34 de 60 | 28 de 60 |
| Duración del aviso (p50) | 1 214 ms | 1 804 ms | 1 810 ms |

- Desde 9.2a el aviso lo escribe Qwen al calentar. Con «de dos a cinco palabras» escribe «Estoy procesando tu
  solicitud.» (1,81 s de audio; «Un momento.» duraba 1,21 s).
- Desde 9.2b la voz dice el aviso entero aunque la respuesta ya esté lista (`voice_output.py:354-362`). Queda un muro
  en 2,5 s + 1,81 s = 4,31 s: 36 de 92 turnos de `final` caen entre 4 290 y 4 340 ms, y la p50 es ese muro.
- En turnos con herramienta pareados (n = 46) el Δ medio `final − inicio` es +601 ms: espera del aviso +421, `decide`
  +262, herramienta −132, continuación +36, voz 0.
- Lo que no es: el resultado de la herramienta creció ~25 fichas (~+20 ms de lectura); la continuación final no cambió
  (Δ p50 −12 ms); la primera toma hablada mide lo mismo (60 caracteres). La voz corta por oración
  (`voice_output.py:71`) y 80 de 82 respuestas son una sola oración.

## 2. El costo fijo de `decide` es la GPU que despierta

`decide` tenía ~230 ms fijos que sus fichas no explican (332 ms + 0,76 ms/ficha frente a 92 ms + 0,67 ms/ficha de la
continuación). No es la petición:

| Petición | Pausa previa | Exceso p50 sobre la recta de la continuación | n |
|---|---|---|---|
| `decide` | < 1,5 s | +26 ms | 50 |
| `decide` | ≥ 3 s | +270 ms | 460 |
| continuación | < 1,5 s | −9 ms | 783 |
| continuación | ≥ 3 s | +237 ms | 57 |

- Es la GPU del notebook (RTX 3060 portátil) que baja de reloj tras 1,5-2 s sin trabajo. En el PC no aparece.
- Descartado con datos: `logprobs` (~20 ms por `decide`), restaurar un checkpoint (≤ 30 ms), la plantilla o el reloj
  rompiendo el prefijo (las fichas evaluadas son las esperadas).
- **Comparabilidad:** desde las 19:43 del 2026-10-24 hay en el notebook una sesión de streaming (Sunshine) que deja la
  GPU en P0 aun ociosa; ese día `decide` tardó 133-167 ms tras 11-20 s de pausa, en el holdout v5 330-440 ms. Desde
  entonces cada cola registra `nvidia-smi` a 1 Hz; una corrida es «fría» si la mediana del prompt de `decide` con menos
  de 40 fichas está en 330-440 ms y «caliente» si está en 135-165 ms.

## 3. Palancas

Simuladas sobre los turnos reales de `final` (el modelo reproduce la p50: 4 310 frente a 4 318 ms):

| Palanca | Dónde | p50 todos los turnos | Estado |
|---|---|---|---|
| Aviso de una a tres palabras (sigue escrito por Qwen) | `mind.py` `NOTICE_ASK`, `NOTICE_MAX_WORDS` | 4 310 → 3 907 ms | `nb-w10-aviso` 3cfe46f68, en int11: medido en e2e de práctica ×3, mediana de las p50 4 400 → 4 035 ms (−365 ms, GPU caliente en los dos brazos) |
| llama-server parcheado (108 → ~48 ms fuera del modelo por petición, 2 en el camino) | `BAXY_MIND_LLAMA_SERVER` | −120 ms | réplica en GPU idéntica (50/50, 2026-10-23); falta decidir llevarlo al producto |
| Primera cláusula a la voz | `voice_output.py:71`, `:220-260`, `:441-455` | 3 907 → 3 743 ms | cambia la prosodia: oído del autor |
| GPU en máximo rendimiento mientras corre BAXY | perfil de NVIDIA (ajuste del sistema) | ~−245 ms por `decide` en el portátil | del autor; no se toca |

Descartadas: resultado de herramienta más corto (< 0,1 s), adelantar la lectura del resultado mientras corre la
herramienta (la herramienta dura 76 ms p50), menos peticiones a llama (el número no cambió desde `inicio`),
decodificación especulativa (cambiaría lo que se muestrea), un pulso CUDA propio desde «Baxy» hasta la decisión (un
segundo contexto CUDA no cabe en los 4 096 MiB con 3 986 ocupados), bajar `top_logprobs` (≤ 20 ms).

Informes completos y scripts: `%TEMP%\claude\nb\cien\lat\H7-desglose.md` y `H7-decide.md` (máquina del notebook).
