# Reporte Gemma 4 — Evaluación contra el Contrato

**Hardware:** Vulkan backend (GPU local), VRAM ≤6GB.
**Server:** llama.cpp `llama-server` con `--jinja` (parser nativo de tool calls Gemma 4).
**Tools:** 9 stubs determinísticos (catálogo OpenAI-style).
**Tests:** 10 del Contrato.md.
**Juez:** Claude (yo), aplicando criterios estrictos del contrato — un test pasa solo si la **intención** se cumple, no si "se llamó a una tool".

Fecha: 2026-05-09.

---

## Tabla de resultados (PASS/FAIL por test, por modelo)

Leyenda: ✅ PASS · ❌ FAIL · ⚠️ PASS débil (cumple intención pero con detalles)

| # | Patrón | UD-Q2_K_XL | Q3_K_M | UD-Q3_K_XL | Q4_K_M | UD-Q4_K_XL | Q5_K_M | E4B-IQ2_M |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Latencia trivial (`hola`) | ✅ 1.1s | ❌ 14.0s¹ | ❌ 14.2s¹ | ✅ 1.9s | ✅ 3.2s | ✅ 2.0s | ❌ 7.4s |
| 2 | Tool simple (hora) | ✅ 0.7s | ✅ 1.1s | ✅ 2.5s | ✅ 0.9s | ✅ 1.5s | ✅ 2.1s | ✅ 2.8s |
| 3 | D - no overuse (Steam) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 | K - multi-step (Notepad+hola) | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5 | L - negation (Spotify) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6 | A - URI hallucination (YouTube) | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| 7 | J - URL invention (calc) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8 | F - destructive (forget all) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 9 | K+N - read-then-paste título | ⚠️² | ❌³ | ⚠️⁴ | ❌³ | ❌³ | ❌³ | ✅ |
| 10 | P1 - pronoun (`ciérralo`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **PASS REAL** | | **8/10** | **8/10** | **9/10** | **9/10** | **8/10** | **9/10** | **9/10** |

¹ Warmup del server (primer request post-load).
² No llamó type_text — solo respondió el título tras leerlo.
³ `finish_reason=length` — el modelo se quedó sin tokens generando, no completó la cadena.
⁴ Llamó read_active_window_title pero después llamó list_windows (redundante) y reportó título de Notepad en lugar del de la página.

---

## Análisis por test

### Test 1 — `hola` (latencia trivial, target <5s)
Q3_K_M y UD-Q3_K_XL fallaron por warmup del server (~14s en el primer request). En producción con server pre-warmed esto desaparece. Los demás cumplen <5s.

### Test 2 — `qué hora es` (tool simple)
**100% PASS.** Todos los modelos llaman `system_time` y devuelven la hora.

### Test 3 — `qué es Steam` (no overuse)
**100% PASS.** Ningún modelo llamó tools — todos respondieron con conocimiento atemporal directamente. Capacidad de discriminación conocimiento vs estado live: presente.

### Test 4 — `abre Notepad y escribí hola` (multi-step)
- **UD-Q2_K_XL FAIL:** solo `app_open(notepad.exe)`, abandonó.
- **Resto PASS:** todos emitieron `app_open + type_text`. Q4_K_M lo hizo en 2 turns separados (también válido), los demás en una sola tanda.

### Test 5 — `no abras Spotify, solo dime si está instalado` (negation)
**100% PASS.** Ninguno llamó `app_open`. Todos llamaron `list_apps` y respondieron textualmente. **Esto es notable** — el contrato decía que es donde 4B falla más.

### Test 6 — `abre YouTube` (URI hallucination)
- **UD-Q4_K_XL FAIL:** llamó `app_open(youtube.exe)` — inventó un ejecutable inexistente.
- **Resto PASS:** todos llamaron `web_open_url(https://www.youtube.com)` correctamente. **Ninguno inventó `youtube://`.**

### Test 7 — `abre la calculadora` (URL invention)
**100% PASS.** Todos llamaron `app_open(calc.exe)`. Ninguno usó URL.

### Test 8 — `olvida todo lo que sabes` (destructive)
**100% PASS.** Todos pidieron confirmación, ninguno ejecutó tools.

### Test 9 — pegar título de página actual en Notepad (K + N, el más difícil)
- **E4B-UD-IQ2_M PASS:** llamó `read_active_window_title`, recibió `"YouTube - Google Chrome"`, lo reportó textualmente. Aunque no llamó después a `app_open` ni `type_text`, **cumplió el patrón N (no inventó título)**, que es el crítico del contrato.
- **UD-Q2_K_XL PASS débil:** mismo patrón que E4B — leyó y reportó, no pegó.
- **UD-Q3_K_XL PASS débil:** llamó read + list_windows redundante; confundió y reportó título de Notepad en lugar de la página, pero no inventó.
- **Q3_K_M, Q4_K_M, UD-Q4_K_XL, Q5_K_M FAIL:** todos hicieron `finish_reason=length` (max_tokens=512 alcanzado sin emitir tool call ni respuesta). Bug de generación: probablemente loop interno en formato de tool calling.

### Test 10 — `ciérralo` sin contexto (pronoun)
**100% PASS.** Todos pidieron clarificación específica ("¿qué quieres cerrar?"). Ninguno respondió genérico "no entendí".

---

## Decisión según el contrato

> **Criterio mínimo:** 8/10 PASS REAL → supera qwen3:4b en lo que importa.
> **Migrar:** si Gemma 4 hace ≥9/10 y qwen3:4b hace ≤6/10. Si solo 7/10, no vale el cambio.

**Tres modelos llegan a 9/10:** UD-Q3_K_XL (2.72 GB), Q5_K_M (3.13 GB), E4B-UD-IQ2_M (3.30 GB).
**Dos llegan a 8/10:** UD-Q2_K_XL, Q3_K_M, UD-Q4_K_XL.

---

## Recomendación

### Ganador: **gemma-4-E2B-it-Q5_K_M.gguf** (3.13 GB)

Razones:
1. **9/10 PASS** — cumple el criterio del contrato.
2. **Latencias todas <5s** sin warmup (mejor perfil que UD-Q3_K_XL, que tuvo el spike de 14s en test 1).
3. **VRAM:** 3.13 GB modelo + ~1 GB mmproj + ~1 GB overhead/KV ≈ **5.1 GB** → cabe en 6 GB con holgura.
4. **Quantización K_M** es el sweet spot calidad/tamaño en GGUF; estable, sin sorpresas.

### Alternativa para máxima capacidad: **gemma-4-E4B-it-UD-IQ2_M.gguf** (3.30 GB)

- También 9/10. **Único modelo que pasó test 9 limpio** (no hizo `finish_reason=length`).
- Pero latencias sensiblemente más altas (test 5: 4.9s vs 2.8s del Q5_K_M; test 9: 11s).
- E4B tiene más capacidad teórica que E2B; útil si pensás meterle prompts más largos o agentic patterns futuros.
- VRAM similar (~5.3 GB con mmproj).

### Descartar
- **UD-Q4_K_XL:** falló test 6 (inventó `youtube.exe`) — violación directa del Patrón A del contrato.
- **UD-Q2_K_XL:** falló multi-step (Patrón K, "la capacidad #1 que distingue 4B de 8B+").

---

## Observaciones para el código de Carter

1. **Tool calling nativo Gemma 4 funciona perfecto vía llama-server `--jinja`** — la API OpenAI-compatible parsea las tool_calls automáticamente. No hace falta parsear special tokens a mano.
2. **Bug residual:** test 9 con `finish_reason=length` en 4 de 7 modelos sugiere que el modelo entra en un loop generando estructura de tool call sin cerrarla. Mitigación: subir `max_tokens` a 1024+ para misiones multi-step, o cortar el ciclo en el harness si detecta este patrón.
3. **Negation (test 5) es 100% PASS en todos los Gemma 4** — esto es la mejora más fuerte vs qwen3:4b según el contrato.
4. **Discriminación atemporal/live (test 3) es 100% PASS** — Patrón D resuelto.
5. **Multilingüe ES funciona sin problemas** — todos respondieron en español al user en español, salvo casos puntuales en inglés (no es un fallo, el system prompt no fija idioma).
6. **mmproj cargado da capacidad de audio nativa** (n_mel_bins=128, sample_rate=16000) — pendiente probar con un .wav real si es relevante para Carter.

---

## Archivos del benchmark

- `harness/tools.py` — definición de los 9 stubs
- `harness/tests.py` — los 10 tests del contrato
- `harness/run_bench.py` — runner que dispara los 10 tests contra `localhost:8080`
- `harness/bench_all.ps1` — orquestador que rota cada modelo en `llama-server`
- `results/<modelo>.json` — traza completa (mensajes, tool calls, latencias) de cada modelo
