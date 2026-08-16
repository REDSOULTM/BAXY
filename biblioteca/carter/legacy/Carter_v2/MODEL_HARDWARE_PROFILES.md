# Carter Hardware Profiles (M2)

Cada perfil define un *budget* de VRAM/RAM y la política de carga. Ningún perfil
permite tener LLM-texto + VLM + STT + TTS pesados simultáneamente residentes; los
budgets *sumados* siempre dejan ≥15% libre del total VRAM para Windows + apps.

## Reglas comunes a todos los perfiles

- **Hard cap** = 0.85 × VRAM total. Cualquier modelo cuya carga estimada empuje
  por encima de este cap no es elegible para el perfil.
- **Una carga a la vez.** El runner serial siempre hace `keep_alive=0` antes de
  cargar el siguiente modelo de gran tamaño.
- **Texto siempre residente** (always-loaded). Visión, STT y TTS se cargan
  *on-demand* y se descargan automáticamente tras `KEEP_ALIVE` segundos sin uso.
- **Fallbacks** son obligatorios si el modelo recomendado falta: el selector
  baja un peldaño (p.ej. qwen3:14b → qwen3:8b → qwen3:4b → qwen3:1.7b).

## PROFILE_CPU_ONLY

| Item | Valor |
|---|---|
| VRAM total | 0 |
| RAM mínima | 8 GB (16 GB recomendado) |
| VRAM budget texto | n/a (todo CPU) |
| VRAM budget visión | n/a |
| VRAM budget STT | n/a |
| VRAM budget TTS | n/a |
| Contexto recomendado | 4096 |
| Cuantización | Q4_K_M / Q4_0 |
| Concurrent models | 1 (texto); STT/TTS solo si RAM ≥ 12 GB |
| Always-loaded | LLM texto pequeño (1.7B / 3B) |
| On-demand | Whisper-tiny CPU, Piper TTS |
| Unload policy | `keep_alive=60s` |

## PROFILE_6GB_COMMON

| Item | Valor |
|---|---|
| VRAM total | 6 GB |
| Hard cap | 5.1 GB |
| RAM mínima | 16 GB |
| VRAM budget texto | 4.0 GB |
| VRAM budget visión (on-demand) | 4.5 GB (después de unload de texto, no concurrente) |
| VRAM budget STT | 0.7 GB |
| VRAM budget TTS | 0.3 GB |
| Contexto | 8192 |
| Cuantización | Q4_K_M |
| Concurrent models GPU | 1 LLM texto + 1 ligero (STT-tiny ó TTS-Piper) |
| Always-loaded | qwen3:4b (o qwen3:1.7b si falta) |
| On-demand | moondream para visión (con unload del texto antes), Whisper-tiny GPU, Piper |
| Unload policy | `keep_alive=120s` |

## PROFILE_8GB_GAMER

| Item | Valor |
|---|---|
| VRAM total | 8 GB |
| Hard cap | 6.8 GB |
| RAM mínima | 16 GB |
| VRAM budget texto | 5.5 GB |
| VRAM budget visión (on-demand) | 5.5 GB (no concurrente con texto residente) |
| VRAM budget STT | 1.0 GB |
| VRAM budget TTS | 0.3 GB |
| Contexto | 8192 |
| Cuantización | Q4_K_M |
| Always-loaded | qwen3:8b ó granite3.3:8b (si tools < umbral, fallback qwen3:4b) |
| On-demand | minicpm-v ó moondream, Whisper-small GPU, Piper |
| Unload policy | `keep_alive=180s` |

## PROFILE_10GB_BALANCED

| Item | Valor |
|---|---|
| VRAM total | 10 GB |
| Hard cap | 8.5 GB |
| RAM mínima | 16 GB |
| VRAM budget texto | 7.0 GB |
| VRAM budget visión | 6.5 GB on-demand (unload texto) |
| VRAM budget STT | 1.5 GB |
| Contexto | 16384 |
| Always-loaded | qwen3:8b (Q4_K_M) |
| On-demand | qwen2.5vl:7b grounding, faster-whisper-small, Piper |
| Unload policy | `keep_alive=300s` |

## PROFILE_12GB_POWER

| Item | Valor |
|---|---|
| VRAM total | 12 GB |
| Hard cap | 10.2 GB |
| RAM mínima | 16 GB |
| VRAM budget texto | 7.5 GB |
| VRAM budget visión concurrente | 4 GB (moondream) ó 6 GB (qwen2.5vl con unload temporal de contexto) |
| VRAM budget STT | 2.0 GB |
| Contexto | 16384 |
| Always-loaded | qwen3:8b |
| On-demand concurrente | moondream + faster-whisper-small simultáneo |
| Unload policy | `keep_alive=600s` |

## PROFILE_16GB_CREATOR (RTX 4060 Ti — usuario actual)

| Item | Valor |
|---|---|
| VRAM total | 16 GB |
| Hard cap | 13.6 GB |
| RAM mínima | 16 GB |
| VRAM budget texto | 8.0 GB (qwen3:8b o granite3.3:8b) |
| VRAM budget texto opt | 11 GB (qwen3:14b Q4_K_M) intercambiable por env |
| VRAM budget visión concurrente | 6 GB (qwen2.5vl) — admite texto + visión a la vez |
| VRAM budget STT | 2.5 GB (faster-whisper-medium ó distil-large) |
| VRAM budget TTS | 0.5 GB (Piper) ó 2 GB (XTTSv2) |
| Contexto | 16384 (32k posible bajo demanda) |
| Always-loaded | qwen3:8b (default) — ENV `CARTER_TEXT_MODEL=qwen3:14b` para Power Mode |
| On-demand | qwen2.5vl:7b, llava:7b, faster-whisper, Piper |
| Concurrent allowed | LLM texto + 1 modal (visión XOR voz STT) |
| Unload policy | `keep_alive=600s` LLM, `60s` modales |

## PROFILE_24GB_PLUS

| Item | Valor |
|---|---|
| VRAM total | ≥ 24 GB |
| Hard cap | 20.4 GB |
| RAM mínima | 32 GB |
| VRAM budget texto | 12 GB (qwen3:14b Q4 ó qwen2.5:32b Q4) |
| VRAM budget texto opt | 22 GB (qwen2.5:32b Q4_K_M en P_24) |
| VRAM budget visión concurrente | 6 GB |
| VRAM budget STT | 6 GB (large-v3) |
| VRAM budget TTS | 2 GB (XTTSv2) |
| Contexto | 32768 |
| Always-loaded | qwen3:14b |
| Concurrent allowed | LLM + visión + STT residentes con margen |
| Unload policy | `keep_alive=900s` LLM, `300s` modales |

---

## Resumen de presupuestos por perfil

| Perfil | VRAM | Cap | Texto MB | Visión MB | STT MB | TTS MB | Concurrencia |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ONLY | 0 | 0 | – | – | – | – | 1 (RAM) |
| 6GB | 6144 | 5222 | 4096 | 4500* | 700 | 300 | 1 GPU + ligeros CPU |
| 8GB | 8192 | 6963 | 5632 | 5632* | 1024 | 300 | 1 GPU pesado |
| 10GB | 10240 | 8704 | 7168 | 6656* | 1536 | 300 | 1 GPU pesado |
| 12GB | 12288 | 10444 | 7680 | 4096-6144 | 2048 | 300 | LLM + 1 modal |
| 16GB | 16384 | 13926 | 8192-11264 | 6144 | 2560 | 512-2048 | LLM + 1 modal |
| 24GB+ | 24576+ | 20889 | 12288-22528 | 6144 | 6144 | 2048 | LLM + 2 modales |

*on-demand con unload del LLM texto. La visión grande no es concurrente con texto en perfiles ≤ 10 GB.
