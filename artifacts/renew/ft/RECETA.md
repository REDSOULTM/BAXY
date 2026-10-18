# Receta del ajuste fino de Qwen3.5-4B para BAXY (2026-10-18)

Investigada por tres agentes con fuentes (informes completos fuera del repo, en `F:/BAXYeval/ft_v1/receta/`:
`A_qwen35_tooling.md`, `B_lora_toolcalling.md`, `C_merge_quant.md`) y comprobada en el PC donde se indica.

## El modelo y lo que ve la mente

- `Qwen/Qwen3.5-4B` es el modelo post-entrenado (no hay `-Instruct`); todos los GGUF de 4B lo declaran como base
  ([tarjeta](https://huggingface.co/Qwen/Qwen3.5-4B)). El de producción es byte a byte el `Qwen3.5-4B-Q4_K_M.gguf` de
  `unsloth/Qwen3.5-4B-GGUF`, con la imatrix de Unsloth y una mezcla de tipos de tensor propia (comprobado: sha256 y
  `llama-quantize --dry-run`).
- Arquitectura híbrida: 32 capas, 24 Gated DeltaNet y 8 de atención completa (3:1), oculto 2560, vocabulario 248.320
  con embeddings atados, torre de visión y cabeza MTP en el mismo checkpoint (config.json; Qwen3_5ForCausalLM carga
  sólo el texto: 4,2B parámetros).
- La mente manda 176 herramientas y su prompt de sistema por `/v1/chat/completions` con la plantilla Jinja del GGUF
  (la de Qwen con el arreglo de argumentos de Unsloth y el razonamiento apagado por defecto). Los datos se renderizan
  con esa misma plantilla en llama-server (`/apply-template`) y se tokenizan con él; el prefijo común son 42.734 tokens.

## Método

- **LoRA bf16, no QLoRA.** Unsloth: «It is not recommended to do QLoRA (4-bit) training on the Qwen3.5 models»
  ([guía](https://unsloth.ai/docs/models/qwen3.5/fine-tune)). QLoRA en general: Dettmers et al. 2023
  ([arXiv:2305.14314](https://arxiv.org/abs/2305.14314)).
- **Rango y alfa**: r=32, α=32, sin dropout; LoRA en todas las capas lineales, incluido el MLP, y LR ≈10× la de FT
  completo («LoRA Without Regret», [Thinking Machines 2025](https://thinkingmachines.ai/blog/lora/)); LoRA aprende
  menos y olvida menos que FT completo, y el olvido crece con épocas y rango
  ([Biderman et al. 2024, arXiv:2405.09673](https://arxiv.org/abs/2405.09673)).
- **Módulos**: `q,k,v,o_proj` (8 capas de atención) + `in_proj_qkv, in_proj_z, out_proj` (24 capas DeltaNet; la lista
  habitual de 7 módulos las deja fuera, [Axolotl](http://docs.axolotl.ai/docs/models/qwen3.5.html)) +
  `gate, up, down_proj`; nunca visión, embeddings ni `lm_head` (atados).
- **Optimización**: LR 1e-4 con coseno hasta el 10 % y 5 % de calentamiento, norma de gradiente 1, lote efectivo 16,
  ≤2 épocas (receta B, §1).
- **Pérdida sólo en la respuesta** del asistente, hasta `<|im_end|>` (TRL `assistant_only_loss`,
  [docs](https://huggingface.co/docs/trl/sft_trainer)).
- **El prefijo real de 42,7k tokens, sin recortar herramientas**: transformers 5.20 continúa Qwen3.5 desde una caché
  (atención y estados de DeltaNet). Por paso, el prefijo corre sin gradiente con los pesos LoRA del momento; cada
  muestra corre sólo su sufijo sobre una vista de sólo lectura de esa caché, con checkpointing por capa. Comprobado: la
  pérdida coincide con un pase completo dentro del redondeo bf16 (0,5-1,5 %); 27 s el prefijo y 0,65 s por muestra en
  la 4060 Ti. Brecha documentada: sin gradiente a través de las posiciones del prefijo.
- **Windows**: con la VRAM llena el controlador desborda a la RAM del sistema en vez de fallar (pasos de 10 min); el
  entrenador devuelve la caché del asignador tras el prefijo y por muestra (pico 11,8 GiB).

## Datos

- **Mezcla** (receta B, §2-3): llamadas correctas ~60 %, preguntas ~12 % (los modelos ajustados tienden a inventar el
  dato en vez de preguntar), «no lo hago» ~10 %, charla y texto pegado ~8 %, y réplica de las propias respuestas del
  modelo base ~8 % para no olvidar (la réplica propia olvida menos que datos públicos). When2Call: 2:1 de llamadas
  frente a no llamadas ([arXiv:2504.18851](https://arxiv.org/abs/2504.18851)); Hammer: ~10 % de irrelevancia
  ([arXiv:2410.04587](https://arxiv.org/abs/2410.04587)).
- **Semilla**: el conjunto de ajuste etiquetado de la auditoría; el objetivo es la salida del propio modelo que el
  juez da por buena y sin afirmar nada no hecho (rechazo con autodestilación), remuestreada para los que fallan.
- **Sintéticos**: cinco agentes desde el catálogo (`tools_lote3.json`, `ProductCatalog.cs`, los handlers para los
  códigos de error reales), nunca desde frases del dueño; validados contra el esquema JSON de cada herramienta.
- **Réplica del latido**: escenas sintéticas nuevas con la decisión del modelo base.
- **Fuga** (regla 4), contra todos los bancos, sellados incluidos, sin imprimir nunca su texto: igualdad normalizada,
  6-gramas de palabras, 50 % de 4-gramas, Jaccard de 4-gramas de caracteres ≥0,55; y una pasada semántica
  (paraphrase-multilingual-MiniLM-L12-v2): coseno ≥0,90, o ≥0,85 con palabras de contenido en común. Los 13-gramas
  clásicos no sirven para pedidos de 5-15 palabras (receta B, §5).

## Fusión, cuantización y evaluación

- Fusión sobre los safetensors en el dtype de cada tensor (`merge_and_unload` de PEFT redondea los tensores float32 de
  DeltaNet: comprobado, 24 `ssm_norm` cambian hasta un 0,3 % con un LoRA nulo).
- `convert_hf_to_gguf.py` de llama.cpp b11609 (la versión de producción) con `--no-mtp`, plantilla de producción
  embebida, y `llama-quantize` Q4_K_M con la mezcla de tipos de producción e imatrix (la de Unsloth para cribar
  checkpoints; propia para el final). Con imatrix el KLD de Q4_K_M baja de 0,0313 a 0,0282
  ([llama.cpp #5263](https://github.com/ggml-org/llama.cpp/discussions/5263)). Control: el base pasado por este
  pipeline da el mismo tamaño y la misma mezcla que producción.
- El checkpoint se elige por los bancos, no por la pérdida (LIMA, [arXiv:2305.11206](https://arxiv.org/abs/2305.11206)):
  decision2 s0-2, escenas sin tocar + 3 perturbaciones y e2e s0-2 contra la base del día, con el GGUF fusionado y
  cuantizado, no con el adaptador.
