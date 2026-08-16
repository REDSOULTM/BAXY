---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- generated_from_trainer
- dataset_size:11808
- loss:MultipleNegativesRankingLoss
base_model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
widget:
- source_sentence: abre o Netflix
  sentences:
  - 'open a website, URL or web address in a browser; abrir una pagina web, abrir
    github o un sitio, abrir una direccion como python.org o localhost, navegar a
    un enlace, open a link in the browser. TAMBIEN: buscar o comprar un producto o
    juego en una TIENDA WEB (Instant Gaming, Steam store online, Epic Games, GOG,
    Amazon): ir al sitio de la tienda y buscar ahi el juego; find or buy a game on
    an online store website, go to the store site and search for the product'
  - audio volume, raise or lower the sound volume, turn it up or down (subir/bajar
    el volumen, lauter/leiser machen, alza/abbassa il volume, aumenta/diminui o volume,
    monter/baisser le volume); mute and unmute the sound (silenciar, desmutear, stummschalten,
    ton an, couper/rétablir le son, silenciar/reativar o som), system sound, media
    keys, audio devices listing
  - 'WhatsApp messaging: send a message, REPLY/answer a message, open a chat, mandar/responder/contestar
    un mensaje por WhatsApp, respondele/contestale a una persona, escribir a alguien
    en wsp, decirle algo a alguien en whatsapp, mensaje de texto'
- source_sentence: abre configuración y entra a Bluetooth
  sentences:
  - create a local or cloud reminder
  - 'open a website, URL or web address in a browser; abrir una pagina web, abrir
    github o un sitio, abrir una direccion como python.org o localhost, navegar a
    un enlace, open a link in the browser. TAMBIEN: buscar o comprar un producto o
    juego en una TIENDA WEB (Instant Gaming, Steam store online, Epic Games, GOG,
    Amazon): ir al sitio de la tienda y buscar ahi el juego; find or buy a game on
    an online store website, go to the store site and search for the product'
  - 'operate inside an open app: Discord text channel, voice channel, send messages
    in Discord/Slack/Teams, mute or unmute Discord microphone, deafen or undeafen
    Discord, leave a voice call, open or focus a browser, navigate inside a browser/app,
    click a bookmark/favorite/link/result/named control, chain browser actions to
    reach a goal. canal de voz discord, canal de texto discord, mutea mi microfono
    en discord, ensordecer discord, barra de favoritos, marcador, abrir un navegador
    y clickear un favorito'
- source_sentence: list my open tabs
  sentences:
  - list windows, focus, close, minimize, maximize, move, resize
  - create automation routines with manual, cron, or on-app-open triggers
  - play music or a video, pause, stop, next, previous, now playing; reproducir una
    canción o video, poner música, spiel ein Lied ab, metti una canzone, toca uma
    música, mets une chanson, abspielen
- source_sentence: conectate al wifi de casa
  sentences:
  - abrir, cerrar o encontrar un programa o juego ya instalado en esta computadora,
    desde el menú de inicio; open, close or find an installed desktop application
    on this PC by name
  - 'drive a real browser via Playwright: tabs, fill forms, click, extract text'
  - connect to a WiFi network / join wifi / switch wifi network, Bluetooth, display,
    power plans, system settings — conectar/conectarse a una red WiFi
- source_sentence: andá a la página de YouTube
  sentences:
  - 'open a website, URL or web address in a browser; abrir una pagina web, abrir
    github o un sitio, abrir una direccion como python.org o localhost, navegar a
    un enlace, open a link in the browser. TAMBIEN: buscar o comprar un producto o
    juego en una TIENDA WEB (Instant Gaming, Steam store online, Epic Games, GOG,
    Amazon): ir al sitio de la tienda y buscar ahi el juego; find or buy a game on
    an online store website, go to the store site and search for the product'
  - Steam game library, Steam store, launch installed Steam games
  - 'system info, processes and power: current time and date, qué hora es, qué fecha
    es hoy; list running processes, kill or force-close a process, taskkill, mata
    procesos colgados, lista procesos, cierra un proceso; CPU RAM GPU disk; how much
    memory/RAM do I have, free memory, memory usage, RAM usage, cuánta memoria tengo,
    cuánta memoria RAM libre tengo, uso de memoria, memoria del sistema, quanta memória
    tenho, quanto di memoria ho, wie viel Arbeitsspeicher habe ich, combien de mémoire
    RAM; SCREEN/display brightness up/down — subir/bajar el brillo de la pantalla,
    atenuar la pantalla, set screen brightness; battery level, shutdown restart sleep'
pipeline_tag: sentence-similarity
library_name: sentence-transformers
---

# SentenceTransformer based on sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2). It maps sentences & paragraphs to a 384-dimensional dense vector space and can be used for semantic textual similarity, semantic search, paraphrase mining, text classification, clustering, and more.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) <!-- at revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42 -->
- **Maximum Sequence Length:** 128 tokens
- **Output Dimensionality:** 384 dimensions
- **Similarity Function:** Cosine Similarity
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/UKPLab/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'max_seq_length': 128, 'do_lower_case': False}) with Transformer model: BertModel 
  (1): Pooling({'word_embedding_dimension': 384, 'pooling_mode_cls_token': False, 'pooling_mode_mean_tokens': True, 'pooling_mode_max_tokens': False, 'pooling_mode_mean_sqrt_len_tokens': False, 'pooling_mode_weightedmean_tokens': False, 'pooling_mode_lasttoken': False, 'include_prompt': True})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```

Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    'andá a la página de YouTube',
    'open a website, URL or web address in a browser; abrir una pagina web, abrir github o un sitio, abrir una direccion como python.org o localhost, navegar a un enlace, open a link in the browser. TAMBIEN: buscar o comprar un producto o juego en una TIENDA WEB (Instant Gaming, Steam store online, Epic Games, GOG, Amazon): ir al sitio de la tienda y buscar ahi el juego; find or buy a game on an online store website, go to the store site and search for the product',
    'Steam game library, Steam store, launch installed Steam games',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 384]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities.shape)
# [3, 3]
```

<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset


* Size: 11,808 training samples
* Columns: <code>sentence_0</code> and <code>sentence_1</code>
* Approximate statistics based on the first 1000 samples:
  |         | sentence_0                                                                       | sentence_1                                                                         |
  |:--------|:---------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------|
  | type    | string                                                                           | string                                                                             |
  | details | <ul><li>min: 3 tokens</li><li>mean: 10.0 tokens</li><li>max: 46 tokens</li></ul> | <ul><li>min: 9 tokens</li><li>mean: 71.13 tokens</li><li>max: 128 tokens</li></ul> |
* Samples:
  | sentence_0                                       | sentence_1                                                                                                                                                                                                                                                                                                                                                                            |
  |:-------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | <code>abre Notepad y escribe hola con GUI</code> | <code>screenshot, click, type text, hotkeys, scroll, drag with mouse</code>                                                                                                                                                                                                                                                                                                           |
  | <code>schließ den Editor</code>                  | <code>abrir, cerrar o encontrar un programa o juego ya instalado en esta computadora, desde el menú de inicio; open, close or find an installed desktop application on this PC by name</code>                                                                                                                                                                                         |
  | <code>Mets le volume à 25 pour cent</code>       | <code>audio volume, raise or lower the sound volume, turn it up or down (subir/bajar el volumen, lauter/leiser machen, alza/abbassa il volume, aumenta/diminui o volume, monter/baisser le volume); mute and unmute the sound (silenciar, desmutear, stummschalten, ton an, couper/rétablir le son, silenciar/reativar o som), system sound, media keys, audio devices listing</code> |
* Loss: [<code>MultipleNegativesRankingLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss) with these parameters:
  ```json
  {
      "scale": 20.0,
      "similarity_fct": "cos_sim"
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 64
- `per_device_eval_batch_size`: 64
- `num_train_epochs`: 2
- `multi_dataset_batch_sampler`: round_robin

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `overwrite_output_dir`: False
- `do_predict`: False
- `eval_strategy`: no
- `prediction_loss_only`: True
- `per_device_train_batch_size`: 64
- `per_device_eval_batch_size`: 64
- `per_gpu_train_batch_size`: None
- `per_gpu_eval_batch_size`: None
- `gradient_accumulation_steps`: 1
- `eval_accumulation_steps`: None
- `torch_empty_cache_steps`: None
- `learning_rate`: 5e-05
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `max_grad_norm`: 1
- `num_train_epochs`: 2
- `max_steps`: -1
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: {}
- `warmup_ratio`: 0.0
- `warmup_steps`: 0
- `log_level`: passive
- `log_level_replica`: warning
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `save_safetensors`: True
- `save_on_each_node`: False
- `save_only_model`: False
- `restore_callback_states_from_checkpoint`: False
- `no_cuda`: False
- `use_cpu`: False
- `use_mps_device`: False
- `seed`: 42
- `data_seed`: None
- `jit_mode_eval`: False
- `use_ipex`: False
- `bf16`: False
- `fp16`: False
- `fp16_opt_level`: O1
- `half_precision_backend`: auto
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `local_rank`: 0
- `ddp_backend`: None
- `tpu_num_cores`: None
- `tpu_metrics_debug`: False
- `debug`: []
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_prefetch_factor`: None
- `past_index`: -1
- `disable_tqdm`: False
- `remove_unused_columns`: True
- `label_names`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `fsdp`: []
- `fsdp_min_num_params`: 0
- `fsdp_config`: {'min_num_params': 0, 'xla': False, 'xla_fsdp_v2': False, 'xla_fsdp_grad_ckpt': False}
- `fsdp_transformer_layer_cls_to_wrap`: None
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `deepspeed`: None
- `label_smoothing_factor`: 0.0
- `optim`: adamw_torch
- `optim_args`: None
- `adafactor`: False
- `group_by_length`: False
- `length_column_name`: length
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `skip_memory_metrics`: True
- `use_legacy_prediction_loop`: False
- `push_to_hub`: False
- `resume_from_checkpoint`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_private_repo`: False
- `hub_always_push`: False
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `include_inputs_for_metrics`: False
- `eval_do_concat_batches`: True
- `fp16_backend`: auto
- `push_to_hub_model_id`: None
- `push_to_hub_organization`: None
- `mp_parameters`: 
- `auto_find_batch_size`: False
- `full_determinism`: False
- `torchdynamo`: None
- `ray_scope`: last
- `ddp_timeout`: 1800
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `dispatch_batches`: None
- `split_batches`: None
- `include_tokens_per_second`: False
- `include_num_input_tokens_seen`: False
- `neftune_noise_alpha`: None
- `optim_target_modules`: None
- `batch_eval_metrics`: False
- `eval_on_start`: False
- `eval_use_gather_object`: False
- `prompts`: None
- `batch_sampler`: batch_sampler
- `multi_dataset_batch_sampler`: round_robin

</details>

### Framework Versions
- Python: 3.11.15
- Sentence Transformers: 3.3.1
- Transformers: 4.44.2
- PyTorch: 2.6.0+cu124
- Accelerate: 1.13.0
- Datasets: 2.21.0
- Tokenizers: 0.19.1

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### MultipleNegativesRankingLoss
```bibtex
@misc{henderson2017efficient,
    title={Efficient Natural Language Response Suggestion for Smart Reply},
    author={Matthew Henderson and Rami Al-Rfou and Brian Strope and Yun-hsuan Sung and Laszlo Lukacs and Ruiqi Guo and Sanjiv Kumar and Balint Miklos and Ray Kurzweil},
    year={2017},
    eprint={1705.00652},
    archivePrefix={arXiv},
    primaryClass={cs.CL}
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->