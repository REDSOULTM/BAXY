# 09 — Decisiones arquitecturales

Todas las decisiones técnicas tomadas durante el proyecto, con justificación medida o citada.

---

## Decisión 1: Modelo ganador = E4B-Q6_K

**Alternativas evaluadas:**
- E2B (todas las quants): bajo techo de calidad — 80-90% en bench Fase 2
- E4B-Q4_K_M: 93.3%, ahorra 1 GB VRAM
- E4B-Q5_K_M: 91.6%, balance medio
- **E4B-Q6_K: 95% — ganador**
- E4B-Q8_0: 91.6% — Q8 NO aporta sobre Q6 medido
- 26B-A4B variantes: 88-93%, requieren 13+ GB VRAM
- 31B variantes: 1-21% — destruidas por cuantización agresiva

**Justificación:** mejor PASS rate dentro del límite de 8 GB VRAM efectivo en consumer GPU.

---

## Decisión 2: Backend = llama.cpp CUDA, no Vulkan

**Comparado:** llama.cpp Vulkan vs CUDA b9090.
**Resultado medido:** CUDA es 30-40% más rápido en NVIDIA. Backend importa.
**Decisión:** todos los benchmarks y producción Carter en CUDA build.

Ver [05_latencia_y_alexa_tier/](../05_latencia_y_alexa_tier/) para datos.

---

## Decisión 3: Runtime = llama.cpp, no vLLM

**vLLM ofrece:**
- 3× speedup MTP drafters disponibles ya
- Audio HTTP nativo funcional (issue #21868 no aplica)

**Pero:**
- Requiere WSL2 + Docker para Windows
- 12 GB descarga (formato HF, no GGUF)
- Mantenimiento operacional más alto
- Inviable para usuarios no-técnicos

**Decisión para Carter (producto distribuible):** llama.cpp como runtime único. Aceptar techo de velocidad actual. Cuando llama.cpp incorpore MTP (proyectado 3-6 meses), Carter gana 3× transparente.

---

## Decisión 4: Sampling = oficial Google sin alterar

```python
SAMPLING = {
    "temperature": 1.0,    # No bajar — Gemma 4 entrenado para esto
    "top_p": 0.95,
    "top_k": 64,
    "repeat_penalty": 1.0, # NO usar 1.1 default Ollama
    "max_tokens": 1280,    # Subido de 768 default
}
```

**max_tokens=1280:** mi versión v6 reveló que 768 causaba `finish_reason=length` con empty replies en multi-step. Subir a 1280 los eliminó.

**T=1.0 (no bajar):** Gemma 4 fue DPO/RLHF tuned a T=1.0. Bajar a 0.7 degrada, no mejora.

---

## Decisión 5: Tools = consolidated 16 composite

**60 tools individuales:** funciona pero no escala.
**16 composite con discriminator `action` enum:** mismo PASS rate, -68% tokens, escalable a 200+ sub-acciones.

Ver [06_consolidacion_tools/](../06_consolidacion_tools/) para detalle.

**Decisión Carter:** soportar ambos catálogos vía `CARTER_TOOL_CATALOG=individual|consolidated`. Default `individual` para no romper código existente, recomendado `consolidated` para Carter v5.

---

## Decisión 6: NO multi-modelo pipeline

**Considerado:** router LLM externo + tool selector + conversational.

**Rechazado por:**
1. Latencia 2-3× sin beneficio (cada modelo agrega ~1-2s).
2. Router accuracy 76% (CARGO paper) → 24% queries mal-clasificadas.
3. Multi-agent puede amplificar errores 17× (paper Why Multi-Agent Systems Fail).
4. Gemma 4 26B-A4B YA tiene routing interno (128 experts, top-8). Mejor que router externo.

**Decisión:** modelo único + system_prompt iterado. Para escalar tools: dynamic loading o consolidated.

---

## Decisión 7: NO partir el system_prompt en tiers

**Considerado:** system_prompt SIMPLE/MEDIA/COMPUESTA según query type.

**Rechazado por:**
- Mi bench actual con prompt monolítico (3500 tokens) = **540/540**.
- Partirlo agrega latencia de routing pre-LLM.
- Research [Anthropic + GitHub MCP] sugiere reducir tools, no partir prompts.

**Decisión:** mantener system_prompt único. Si Carter v5 escala mucho, considerar **rule-based routing pre-LLM** (regex + keywords, ~0.5ms) que selecciona tools relevantes — NO router LLM.

---

## Decisión 8: NO `--reasoning off`

**v13 probó:** `--reasoning off` flag.
**Resultado:** -1.5pp regresión vs v12.

**Causa investigada:** mi build llama.cpp b9090 incluye PR #21418 (specialized Gemma 4 parser) que ya maneja thinking implícitamente. Activar `--reasoning off` interfiere con el parser.

**Decisión:** sin flag. El parser nativo hace el trabajo.

---

## Decisión 9: NO strip `assistant.content` cuando hay `tool_calls`

**v13 probó:** strip de content. Basado en doc Google "thoughts must not be added before next user turn".

**Resultado:** -1.5pp regresión.

**Causa:** mi build b9090 ya tiene PR #21418 que strippea thinking del content automáticamente. El content que llega ES la respuesta natural útil, no thinking.

**Decisión:** preservar `assistant.content` tal cual viene del modelo.

---

## Decisión 10: Audio nativo NO reemplaza Whisper

**Medido:** 2/5 PASS en español rioplatense con Gemma 4 audio nativo.
**Whisper-large-v3:** ~95% en mismo idioma.

**Decisión:** mantener Whisper para STT en Fase 1 Carter. Reevaluar audio nativo en 3-6 meses.

---

## Decisión 11: KV cache F16 (no Q8)

**Tentado:** `--cache-type-k q8_0 --cache-type-v q8_0` para ahorrar VRAM.

**Rechazado por:** [localbench benchmark](https://localbench.substack.com/p/kv-cache-quantization-benchmark) confirma Gemma 4 = más sensible a KV quant tested (KL 0.377 en 26B con q8_0).

**Decisión:** F16 KV cache. Si necesario ahorrar VRAM, bajar context size primero (`-c 8192` en lugar de 16384).

---

## Decisión 12: Mmproj F16 SIEMPRE (no comprimir)

**Tentado:** mmproj-Q8 o Q4 para ahorrar VRAM.

**Rechazado por:** mmproj quantization rompe vision/audio según docs Unsloth + research. F16 es el formato recomendado por HuggingFace incluso con modelo principal Q4.

**Decisión:** mmproj-F16 obligatorio. Si no se usa vision/audio, omitir `--mmproj` enteramente (ahorra 0.92 GB).

---

## Decisión 13: Verifiers reales en Carter (no en bench)

**Bench (este repo):** stubs determinísticos. Mide al modelo, no al SO.
**Carter (otro repo):** verifiers reales obligatorios — `EnumWindows`, `IAudioEndpointVolume.GetMasterVolumeLevelScalar`, etc.

**Decisión:** documentar en `REPORTE_GEMMA4_PARA_CARTER.md` la lista de verifiers que Carter debe wirear, separado del bench. Sin verifiers, Carter está vulnerable a fake success (Valor 3 del Contrato).

---

## Decisión 14: Streaming SSE en Carter

**Bench:** no necesita streaming (sólo mide PASS final).
**Carter:** debe usar `stream: true` para que primer token sea visible en ~500ms en lugar de esperar p99 final.

**Decisión:** llama-server soporta streaming nativo. Carter wire SSE chunks → UI updates incrementales + estados intermedios ("Llamando a app_open...").
