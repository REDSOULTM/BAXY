# Auditoría de licencias — viabilidad COMERCIAL

Total: **511 paquetes**. Generado por scripts/_diag/_license_audit.py.

## ⚡ ANÁLISIS: qué BLOQUEA de verdad (cruce con el código de prod)

La lista cubre TODO el venv de **desarrollo** (511 paquetes, con experimentos). Para vender
importa la **clausura SHIPEADA**, no el venv dev. Cruzando con `gemma4_agent/` (lo que se importa):

### 🔴 1 BLOQUEANTE REAL
- **`piper-tts` 1.4.2 (TTS)** — `from piper import PiperVoice` se **importa** en `voice/tts.py`
  (LINKED). El pip metadata dice **GPL-3.0-or-later** (el rewrite *piper1-gpl*). Un doc viejo del
  repo dice "MIT" → **desactualizado** (el Piper de rhasspy era MIT; el 1.4.x es GPL).
  - **Impacto:** GPL **linkeado** → el producto vendido debería ser open-source. **Bloquea vender propietario.**
  - **Fixes:** (a) **aislar por subprocess** (correr el binario `piper` por CLI = agregación, GPL OK,
    no derivado); (b) **reemplazar** por TTS Apache/MIT (Kokoro=Apache, Piper-viejo MIT, etc.);
    (c) open-source el producto. → **Recomendado (a) o (b).**

### 🟢 GPL/NC que NO bloquean (no shipeados / excepción / redistribuibles)
- **`encodec` (CC-BY-NC), `pedalboard` (GPL), `Unidecode`/`pysrt`/`num2words` (GPL):** NO se
  importan en `gemma4_agent/` (solo en docs) → **transitivos muertos** (de experimentos coqui-TTS).
  No se shipean si el build usa la clausura mínima. Confirmar que pyinstaller no los meta.
- **`MouseInfo`/`PyMsgBox` (GPL):** deps de PyAutoGUI; el prod usa **SendInput/win32**, NO pyautogui
  (`dependency.py` solo lo lista como opcional). Confirmar que no se bundlea.
- **`pyinstaller` (GPLv2):** **build tool** con excepción de bootloader → el `.exe` puede ser
  propietario. **OK.**
- **Intel (`mkl`/`tbb`/`intel-openmp`) + NVIDIA (`cuda-nvrtc`):** runtime libs **redistribuibles** con
  atribución (bundladas por numpy/torch). **OK** (revisar el EULA, es estándar).

### ❓ Los 104 "REVISAR" = metadata ambigua, casi todos permisivos conocidos
(attrs, click, cryptography=Apache/BSD, pydantic=MIT, scikit-learn=BSD, playwright=Apache, …).
Revisar los pocos raros; el grueso es Apache/MIT/BSD.

### ✅ Veredicto + acción
**El stack core (Gemma 4 Apache-2.0 + MediaPipe + OpenCV + Whisper + llama.cpp + Tesseract +
sentence-transformers) es permisivo → VENDIBLE.** Para lanzar:
1. **Resolver `piper-tts`** (subprocess o reemplazo Apache/MIT) — **único bloqueante real**.
2. **Build con clausura mínima** (no el venv dev de 511) → los transitivos GPL/NC muertos no se shipean.
3. `pip-licenses` sobre la **clausura del build** + `THIRD_PARTY_LICENSES.md` con atribuciones.

---


## Resumen

- 🚫 **AGPL**: 0
- 🚫 **GPL**: 8
- 🚫 **NON-COMMERCIAL**: 5
- ⚠️ **LGPL**: 8
- ✅ **GPL-EXCEPTION**: 1
- ❓ **REVISAR**: 104
- ✅ **OK**: 385

## 🚫 BLOQUEANTES para vender (AGPL/GPL/non-commercial)

- **MouseInfo** 0.1.3 — `GPL` — GPLv3+ | GNU General Public License v3 or later (GPLv3+)
- **pedalboard** 0.9.22 — `GPL` — GNU General Public License v3 (GPLv3)
- **piper-tts** 1.4.2 — `GPL` — GPL-3.0-or-later
- **pyinstaller** 6.14.2 — `GPL` — GNU General Public License v2 (GPLv2)
- **pyinstaller-hooks-contrib** 2025.6 — `GPL` — Apache Software License | GNU General Public License v2 (GPLv2)
- **PyMsgBox** 2.0.1 — `GPL` — GNU General Public License v3 or later (GPLv3+)
- **pysrt** 1.1.2 — `GPL` — GPLv3 | GNU General Public License (GPL)
- **Unidecode** 1.4.0 — `GPL` — GPL | GNU General Public License v2 or later (GPLv2+)
- **encodec** 0.1.1 — `NON-COMMERCIAL` — Creative Commons Attribution-NonCommercial 4.0 International
- **intel-openmp** 2021.4.0 — `NON-COMMERCIAL` — Intel End User License Agreement for Developer Tools | Other/Proprietary License
- **mkl** 2021.4.0 — `NON-COMMERCIAL` — Intel Simplified Software License | Other/Proprietary License
- **nvidia-cuda-nvrtc-cu12** 12.9.86 — `NON-COMMERCIAL` — LicenseRef-NVIDIA-Proprietary | Other/Proprietary License
- **tbb** 2021.11.0 — `NON-COMMERCIAL` — Intel Simplified Software License | Other/Proprietary License

## ⚠️ LGPL (OK por dynamic-linking, no modificar la lib)

- chardet 5.2.0 — LGPL | GNU Lesser General Public License v2 or later (LGPLv2+)
- crc32c 2.8 — LGPL-2.1-or-later | GNU Lesser General Public License v2 or later (LGPLv2+)
- cssutils 2.11.1 — GNU Library or Lesser General Public License (LGPL)
- frozendict 2.4.6 — LGPL v3 | GNU Lesser General Public License v3 (LGPLv3)
- num2words 0.5.14 — LGPL | GNU Library or Lesser General Public License (LGPL)
- PyQt6-Qt6 6.11.0 — LGPL v3
- pystray 0.19.5 — LGPLv3 | GNU Lesser General Public License v3 (LGPLv3)
- python-bidi 0.6.9 — GNU Library or Lesser General Public License (LGPL)

## ❓ REVISAR a mano (metadata ambigua)

- aistudio-sdk 0.3.8 — UNKNOWN
- annotated-doc 0.0.4 — (sin metadata)
- argon2-cffi 25.1.0 — (sin metadata)
- argon2-cffi-bindings 25.1.0 — (sin metadata)
- asyncpg 0.31.0 — (sin metadata)
- attrs 25.4.0 — (sin metadata)
- av 16.1.0 — (sin metadata)
- build 1.4.0 — (sin metadata)
- carter-v2 0.1.0 — (sin metadata)
- cffi 2.0.0 — (sin metadata)
- click 8.3.1 — (sin metadata)
- comtypes 1.4.16 — (sin metadata)
- coqpit 0.0.17 — (sin metadata)
- cryptography 48.0.0 — (sin metadata)
- cut-cross-entropy 25.1.1 — (sin metadata)
- ddgs 9.14.2 — (sin metadata)
- Flask 3.1.2 — (sin metadata)
- fsspec 2026.1.0 — (sin metadata)
- h5py 3.14.0 — (sin metadata)
- hangul-romanize 0.1.0 — UNKNOWN
- hf_transfer 0.1.9 — (sin metadata)
- httptools 0.7.1 — (sin metadata)
- idna 3.11 — (sin metadata)
- iniconfig 2.3.0 — (sin metadata)
- ipykernel 6.30.1 — (sin metadata)
- jiwer 4.0.0 — (sin metadata)
- joblib 1.5.3 — (sin metadata)
- jsonschema 4.25.1 — (sin metadata)
- jsonschema-specifications 2025.9.1 — (sin metadata)
- jupyter_core 5.8.1 — (sin metadata)
- langgraph 1.1.2 — (sin metadata)
- langgraph-checkpoint 4.0.1 — (sin metadata)
- langgraph-prebuilt 1.0.8 — (sin metadata)
- langgraph-sdk 0.3.11 — (sin metadata)
- llvmlite 0.46.0 — (sin metadata)
- Markdown 3.10.1 — (sin metadata)
- MarkupSafe 3.0.3 — (sin metadata)
- mem0ai 2.0.2 — (sin metadata)
- ml_dtypes 0.5.3 — (sin metadata)
- modelscope 1.36.3 — (sin metadata)
- more-itertools 10.8.0 — (sin metadata)
- msgpack 1.1.2 — (sin metadata)
- namex 0.1.0 — (sin metadata)
- numexpr 2.12.1 — (sin metadata)
- nvidia-cublas-cu12 12.9.2.10 — (sin metadata)
- nvidia-cudnn-cu12 9.22.0.52 — (sin metadata)
- ollama 0.6.2 — (sin metadata)
- onnx 1.21.0 — (sin metadata)
- opentelemetry-api 1.40.0 — (sin metadata)
- opentelemetry-exporter-otlp-proto-common 1.40.0 — (sin metadata)
- opentelemetry-exporter-otlp-proto-grpc 1.40.0 — (sin metadata)
- opentelemetry-proto 1.40.0 — (sin metadata)
- opentelemetry-sdk 1.40.0 — (sin metadata)
- opentelemetry-semantic-conventions 0.61b0 — (sin metadata)
- optree 0.17.0 — (sin metadata)
- packaging 26.0 — (sin metadata)
- pillow 12.1.0 — (sin metadata)
- pip 26.1.1 — (sin metadata)
- playwright 1.55.0 — (sin metadata)
- portalocker 3.2.0 — (sin metadata)
- prettytable 3.17.0 — (sin metadata)
- proglog 0.1.12 — (sin metadata)
- prometheus_client 0.23.1 — (sin metadata)
- pycaw 20251023 — (sin metadata)
- pycparser 3.0 — (sin metadata)
- pydantic 2.12.5 — (sin metadata)
- pydantic_core 2.41.5 — (sin metadata)
- PyJWT 2.12.1 — (sin metadata)
- pynndescent 0.6.0 — (sin metadata)
- pyparsing 3.3.2 — (sin metadata)
- pypdf 6.10.2 — (sin metadata)
- pypiwin32 223 — UNKNOWN
- PyQt6 6.11.0 — (sin metadata)
- pytest 9.0.2 — (sin metadata)
- pyttsx3 2.99 — (sin metadata)
- RapidFuzz 3.14.5 — (sin metadata)
- referencing 0.36.2 — (sin metadata)
- regex 2026.1.15 — (sin metadata)
- rpds-py 0.27.1 — (sin metadata)
- ruff 0.15.12 — (sin metadata)
- scikit-learn 1.7.2 — (sin metadata)
- sentencepiece 0.2.1 — (sin metadata)
- setuptools 80.10.2 — (sin metadata)
- sounddevice 0.5.5 — (sin metadata)
- soxr 1.0.0 — (sin metadata)
- termcolor 3.1.0 — (sin metadata)
- tiktoken 0.9.0 — (sin metadata)
- tomli 2.3.0 — (sin metadata)
- torchao 0.13.0 — (sin metadata)
- trl 0.23.0 — (sin metadata)
- typeguard 4.4.4 — (sin metadata)
- typer 0.24.1 — (sin metadata)
- typer-slim 0.21.1 — (sin metadata)
- typing-inspection 0.4.2 — (sin metadata)
- typing_extensions 4.15.0 — (sin metadata)
- urllib3 2.6.3 — (sin metadata)
- uuid_utils 0.14.1 — (sin metadata)
- uvicorn 0.38.0 — (sin metadata)
- Werkzeug 3.1.5 — (sin metadata)
- wrapt 2.0.1 — (sin metadata)
- xarray 2025.6.1 — (sin metadata)
- xx_sent_ud_sm 3.8.0 — CC BY-SA 3.0
- zipp 3.23.0 — (sin metadata)
- zstandard 0.25.0 — (sin metadata)

## MODELOS (NO los cubre pip — chequear a mano)

- **Gemma 4** (`models/`): Apache 2.0 (desde 2026) ✅
- **mmproj** (visión, parte de Gemma): Apache 2.0 ✅
- **Whisper** (STT): MIT ✅ — pero chequear el checkpoint exacto usado
- **Piper VITS** (TTS): MIT el motor; **cada VOZ tiene su licencia** (algunas CC-BY / no-comercial) — CHEQUEAR la voz que se distribuya
- **Wake-word (LiveKit)**: Apache 2.0 ✅
- **Encoder router (sentence-transformers FT)**: Apache 2.0 (base) ✅
