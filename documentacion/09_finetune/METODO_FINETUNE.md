# Método de fine-tuning — DECISIÓN (research 2026-06-02, evidencia citada)

> **[SUPERADO en el target de modelo] — el RESTO del método sigue vigente.** Este doc
> recomienda el tamaño **E4B**; el proyecto luego **pivoteó a E2B** porque el E4B-FT no
> entra en 4 GB de VRAM (Q4_K_M ~5 GB) — ver `DECISION_MAESTRA_4GB.md`. El **método** en
> sí (LoRA/QLoRA en Unsloth → merge bf16 → GGUF `--outtype bf16` → Q4_K_M + imatrix
> multilingüe, `train_on_responses_only`, gotcha bf16→f16) **se aplicó tal cual al E2B** y
> sigue siendo la receta correcta; solo cambió E4B→E2B y, por VRAM, se usó **QLoRA-4bit**
> (no LoRA-16bit). El FT del E2B ya está entrenado y **desplegado in-place** (ver
> `ESTADO_COMPLETO_2026-06-02.md`). Producto = **Baxy**; el MODELO es Gemma 4 (Google).

**Veredicto [del research original, ver banner]:** entrenar **Gemma 4 E4B-it con LoRA 16-bit** (rank 16-32, target=all-linear) en
**Unsloth**, mergear en **bf16**, convertir a GGUF `--outtype bf16` (NO f16), cuantizar a
**Q4_K_M con imatrix multilingüe** para los 4GB del usuario final. QLoRA = plan B si falta VRAM.
**NO DoRA** (peor calidad a rank bajo + 0 ventaja de latencia post-merge — el "DoRA mejora
latencia" es mito para pipeline que mergea+cuantiza).

## Hechos clave verificados
- **Gemma 4 existe, Apache 2.0** (2-abr-2026). E4B = ~4B activos, dense MatFormer (NO MoE),
  con **audio nativo + function-calling nativo** → ideal para asistente de voz. Repo:
  `google/gemma-4-E4B-it`. Apache 2.0 = **venta comercial OK, fine-tune + redistribución OK**,
  sin copyleft. (Resuelve la nota vieja de memoria "gemma-4 no existe": era alias de naming.)
- **Framework: Unsloth** — guía oficial Gemma 4, ~1.5x speed, ~60% menos VRAM, export GGUF
  directo, parchea gotchas de Gemma 4. E4B-LoRA cabe en ~12GB con
  `use_gradient_checkpointing="unsloth"` + seq 2048 (la cifra "17GB" de su doc es sin eso).
- **Tiempo estimado:** ~30-90 min para 4000 ej × 3 epochs en 4060 Ti + 30-60 min imatrix.
  (Extrapolado — MEDIR con smoke de 200 ej antes del completo.)

## Hiperparámetros anti-overfit (4000 ej, multilingüe)
r=16 (probar 32), alpha=32, dropout=0.05-0.1, lr=2e-4, epochs=2-3 (NO más), weight_decay=0.01,
target=all-linear (attn+MLP; el MLP carga el estilo/personalidad), batch efectivo 16
(2×grad-accum 8), cosine+warmup 5%, max_seq_length=2048. **`train_on_responses_only`** (loss
solo sobre la respuesta/tool-call, no el prompt → no memoriza fraseos = anti-overfit clave).
Held-out diverso POR IDIOMA; ningún idioma fuerte debe degradarse.

## Pipeline
1. Base: `google/gemma-4-E4B-it` (instruct, NO base). Descargado local en
   dataset_finetune/base_model/gemma-4-E4B-it (15GB safetensors + chat_template.jinja).
2. Formato de ejemplos: tool-calls como CAMPO ESTRUCTURADO `message['tool_calls']` (shape
   OpenAI: function.name + arguments), NO texto inventado. Usar el **chat_template.jinja DEL
   MODELO** (NO `get_chat_template("gemma-4")` de Unsloth — ese NO renderiza tool_calls).
   VERIFICADO contra el runtime real (workflow wf_e5c47203): el template del modelo
   (líneas 243-257) renderiza tool_calls → `<|tool_call>call:NAME{...}<tool_call|>`, idéntico
   a deploy (llm_client manda tools vía array OpenAI + parse_tool_calls=true). El dataset NO
   trae args → arguments="{}" (entrena NOMBRE + ORDEN/encadenamiento, no valores).
   `train_on_responses_only` con marcadores Gemma4 `<|turn>user\n` / `<|turn>model\n`.
3. Entrenar **QLoRA-4bit** (load_in_4bit=True). MEDIDO: LoRA-16bit (modelo bf16 ~15GB) NO
   entra en los 16GB de la 4060 Ti → RuntimeError "negligible GPU memory for fused cross
   entropy". QLoRA (4-bit) deja ~11GB libres. Calidad ~idéntica para SFT 4B. finetune_vision_layers=False.
   Cargar con device_map={"": 0} (NO 'auto' → ValueError distribuido en Windows).
4. `save_pretrained_merged("merged-bf16", save_method="merged_16bit")` (QLoRA mergea a bf16 igual).
5. `convert_hf_to_gguf.py merged-bf16 --outtype bf16` (NO f16 — gotcha #1). Converter del commit
   5757c4dcb (==build 9090 de prod) en dataset_finetune/llamacpp_convert/.
6. imatrix multilingüe (es/en/pt/fr/de/it) → `llama-quantize --imatrix ... Q4_K_M`.
   Script: quantize_gguf.py; corpus: make_imatrix_corpus.py (1885 muestras 6 idiomas).
7. Validar EN VIVO (regla #3.5): mismos mensajes + variantes, verificar tool-call + encadenamiento
   + personalidad + los 3 perfiles a11y. Comparar GGUF Q4 vs merged-bf16; si difiere, es precisión, no el FT.

## GOTCHAS (verificados, no repetir)
1. **bf16→f16 downcast BORRA el fine-tune** (issue #7062). Mergear bf16 + `--outtype bf16`.
   El `save_pretrained_gguf` de Unsloth usa f16 por default → preferir ruta manual bf16.
2. Chat template debe COINCIDIR bit a bit entre training y deploy (causa #1 de gibberish).
3. Gemma 4 bugs que Unsloth parchea: use_cache=False→basura; fp16 overflow en audio (usar bf16);
   loss inicial 13-15 es NORMAL en E2B/E4B.
4. NO tunear capas visión/audio (finetune_vision_layers=False).
5. **2-bit (IQ2) es RIESGOSO para tool-calling** (degrada los tags estructurales). Q4_K_M+imatrix
   es la apuesta segura para 4B en 4GB (offload parcial -ngl 20, ~2-3x más lento). Si IQ3,
   imatrix obligatorio + validar por idioma. NO asumir que el FT sobrevive 2-bit.
6. Entrenar sobre bf16/fp16, NUNCA sobre el quant 2-bit. Cuantizar DESPUÉS.
7. Licencia: Gemma 4 Apache 2.0 (libre comercial). Cuidar que el DATASET no arrastre NC/ShareAlike.

## Caveats a medir por mí/el usuario
- Tiempo real en la 4060 Ti específica (smoke 200 ej primero).
- Que Q4_K_M+imatrix preserve tool-calling al 100% en 4GB (medir en vivo, held-out multilingüe).
- Versión de llama.cpp del usuario final soporta el chat template de Gemma 4 (modelo nuevo).

Fuentes completas en el reporte del research (task ae91de975). Decisión tomada 2026-06-02.
