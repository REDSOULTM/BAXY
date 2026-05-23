# HOTFIX 2026-05-17 (Q.0) — CUDA runtime DLLs accessible to faster-whisper

> Sprint chico, alto ROI. Sprint S confirmó que `stt_latency_p95`
> está SKIPPED porque `torch.cuda.is_available()` devuelve False
> Y porque `faster-whisper` falla en inferencia GPU con
> `cublas64_12.dll not found`. Sin Q.0, el bench y todo
> benchmark de latency están sesgados a CPU/int8 — los próximos
> sprints (R2/Q) no se pueden medir honestamente.

---

## Diagnóstico (ya hecho, NO repetir)

Pre-flight ya ejecutado. Estado real del sistema operador:

```
NVIDIA driver:    596.36 (CUDA 13.2 reportado)
CUDA Toolkit:     v13.0 instalado en C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\
                  cublas64_13.dll PRESENTE
PATH:             contiene los dirs CUDA v13.0/bin y v13.0/bin/x64
torch:            2.10.0+cpu (CPU-only wheel — sin CUDA)
ctranslate2:      4.7.1 con CUDA support compiled in
faster-whisper:   1.2.1 (usa ctranslate2)

Smoke probe (faster-whisper device='cuda', float16):
  Loaded on cuda/float16 in 1.1s
  Inference: RuntimeError: Library cublas64_12.dll is not found or cannot be loaded
```

**El problema es simple**: `ctranslate2 4.7.1` busca CUDA 12
runtime (cublas64_**12**.dll) pero el operador tiene CUDA 13
instalado (cublas64_**13**.dll). Versión mismatch.

**El problema NO es**:
- Driver missing — está instalado.
- ctranslate2 sin CUDA — sí tiene support compiled.
- `nvidia-smi` no funciona — funciona.

Copias de cublas64_12.dll que SÍ existen en el disco:
```
C:\Users\usuario\AppData\Local\Programs\Ollama\lib\ollama\cuda_v12\cublas64_12.dll
C:\Users\usuario\AppData\Roaming\PotPlayerMini64\Engine\Faster-Whisper-XXL\_xxl_data\torch\lib\cublas64_12.dll
C:\Users\usuario\AppData\Local\Programs\Python\Python310\Lib\site-packages\~orch\lib\cublas64_12.dll
```

Las primeras 2 son de aplicaciones (Ollama, PotPlayer) — son
funcionales pero NO se pueden referenciar directamente. La 3era
es restos de un pip install/uninstall fallido de torch
(carpeta `~orch` con tilde, marca pip de eliminación pendiente).

## OBJETIVO

Un commit chico. Hacer que `faster-whisper` corra en GPU.

**No es trivial**: hay 3 soluciones posibles, en orden de
preferencia. El agent debe **intentar la primera**; si falla,
escalar a la siguiente; si las 3 fallan, reportar SKIPPED
documentado.

---

## REGLAS GENERALES

1. PortandoLoMejor. Un commit chico, prefijo `chore(env):`.
2. **NO toques** `requirements.txt` salvo para agregar deps
   específicas de CUDA si la solución 1 las requiere.
3. **NO toques** voice pipeline, router, prompts. Pure
   environment setup.
4. **NO instales drivers NVIDIA ni CUDA toolkit** — eso ya está.
   Solo Python packages.
5. Auto-install OK para deps free.
6. NO `git add -A`.
7. **NO toques `torch`**. Reinstalar torch con CUDA es ~2GB de
   download y rompe el environment de otros packages
   (xformers, transformers). Silero VAD funciona en CPU; no
   es bloqueante.

---

## FIX Q.0 — Restaurar CUDA runtime para faster-whisper

### Q.0.1 — Solución 1 (PRIMERA, más limpia)

**Instalar el package `nvidia-cublas-cu12`** de PyPI. Es el
mismo cuBLAS 12 runtime que ctranslate2 busca, distribuido
como Python wheel sin necesidad de tocar CUDA toolkit.

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

`ctranslate2 >= 4.5` automáticamente busca DLLs en los
sitio-packages `nvidia/cublas/bin/` y `nvidia/cudnn/bin/`.
Si la búsqueda funciona, no hay que tocar nada más.

Verificación post-install:

```python
import ctranslate2
print('cuda devices:', ctranslate2.get_cuda_device_count())
# Esperás >= 1

from faster_whisper import WhisperModel
import numpy as np
m = WhisperModel('small', device='cuda', compute_type='float16')
audio = (np.random.randn(16000 * 2) * 2000).astype(np.float32) / 32768
segs, _ = m.transcribe(audio, language='es', beam_size=5)
list(segs)
print('GPU inference OK')
```

Si esto imprime "GPU inference OK" sin raise — **Q.0
resuelto**. Pasar a Q.0.3 (commit).

Si falla con un error distinto a "cublas64_12.dll not found"
(e.g. cudnn missing, otro nombre de DLL), agregar el package
correspondiente:
- `nvidia-cuda-runtime-cu12` para `cudart64_*.dll`.
- `nvidia-cudnn-cu12` para `cudnn_*.dll`.

Si después de instalar los 3 sigue fallando, **escalar a
Solución 2**.

### Q.0.2 — Solución 2 (fallback, copia manual)

`ctranslate2` busca DLLs en su propio dir y en PATH. Si la
Solución 1 falló por algún motivo (e.g. firewall bloqueó pypi),
copiar los DLLs desde Ollama (que ya está instalado y tiene
las versiones correctas):

```python
import shutil
import sys
from pathlib import Path

SRC = Path(r"C:\Users\usuario\AppData\Local\Programs\Ollama\lib\ollama\cuda_v12")
DST = Path(sys.exec_prefix) / "Lib" / "site-packages" / "ctranslate2"

for dll in ["cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll"]:
    src_file = SRC / dll
    if src_file.exists():
        shutil.copy2(src_file, DST / dll)
        print(f"copied {dll}")
```

Trade-off: si Ollama actualiza y mueve esos DLLs, ctranslate2
deja de funcionar (link estático en disco). Solución 1 es
preferida.

### Q.0.3 — Solución 3 (fallback final, downgrade ctranslate2)

Si las soluciones 1 y 2 fallaron, downgrade ctranslate2 a una
versión que use CUDA 13 nativo o que no requiera cublas12.
Verificar con:

```bash
pip index versions ctranslate2 2>&1 | head
```

Y considerar:
```bash
pip install "ctranslate2>=4.4,<4.5"  # versión específica
```

NOTA: esta opción puede romper faster-whisper si tiene un pin
duro a >=4.5. Verificar `pip show faster-whisper | grep Requires`
antes de hacer downgrade.

### Q.0.4 — Limpieza de los tilde files (sin riesgo)

Independientemente de cuál solución funcione, limpiar las
carpetas con tilde de pip install/uninstall fallidos. Son
basura que no se usa:

```bash
find /c/Users/usuario/AppData/Local/Programs/Python/Python310/Lib/site-packages -maxdepth 1 -name "~*" -type d 2>&1
```

Si el output muestra `~orch`, `~rch`, `~1rch`, `~=rch` — borrarlos:

```bash
# CUIDADO: confirmar visualmente cada path antes de rm.
rm -rf /c/Users/usuario/AppData/Local/Programs/Python/Python310/Lib/site-packages/~orch
rm -rf /c/Users/usuario/AppData/Local/Programs/Python/Python310/Lib/site-packages/~rch
# etc
```

Esto NO afecta el sprint — es limpieza de tech debt previa.
Hacelo solo si tenés certeza visual de que es basura tilde.

### Q.0.5 — Verificación end-to-end

Después de aplicar la solución que funcionó, **correr el bench
otra vez**:

```bash
python scripts/bench.py
```

Expectativa:
- `stt_latency_p95`: ahora medido, NO SKIPPED. Resultado
  PASS si p95 ≤ 1.2s, o FAIL si más alto.

Si `stt_latency_p95` sigue SKIPPED con la misma razón
"CUDA not available (fix DLL...)", revisar:
- ¿`bench.py` está chequeando `torch.cuda.is_available()` (que
  sigue siendo False con torch CPU-only)?
- Si sí, **ESE es el bug a fixear**: el check del bench
  debería ser sobre ctranslate2, no torch.

### Q.0.6 — Fix del check si Q.0.5 lo revela

Si el bench sigue skipeando incluso con faster-whisper
funcionando, **actualizar `scripts/bench.py::measure_stt_latency_p95`**:

```python
# ANTES:
try:
    import torch  # type: ignore
except ImportError:
    return ThresholdResult(... note="torch not installed")
if not torch.cuda.is_available():
    return ThresholdResult(... note="CUDA not available")

# DESPUÉS:
# Sprint Q.0: torch is CPU-only on this system but ctranslate2
# (used by faster-whisper) has its own CUDA detection. We probe
# ctranslate2 directly — that's what actually matters for STT
# latency on the production pipeline.
try:
    import ctranslate2  # type: ignore
except ImportError:
    return ThresholdResult(
        ..., note="ctranslate2 not installed",
    )
if ctranslate2.get_cuda_device_count() < 1:
    return ThresholdResult(
        ..., note="No CUDA devices detected by ctranslate2",
    )
# Probe that inference actually works (not just device count):
try:
    from faster_whisper import WhisperModel
    _probe = WhisperModel("tiny", device="cuda", compute_type="float16")
    import numpy as np
    _audio = (np.random.randn(16000) * 100).astype(np.float32) / 32768
    list(_probe.transcribe(_audio, language="es", beam_size=1)[0])
except Exception as exc:
    return ThresholdResult(
        ..., note=f"GPU inference probe failed: {exc}",
    )
# At this point, CUDA inference works. Proceed with the
# benchmark using the real StreamingSTT.
```

Esto se hace solo si Q.0.5 lo revela necesario. NO modificar el
bench preventivamente.

### Q.0.7 — Tests

`gemma4_agent/test_cuda_availability.py`:

```python
"""Q.0: ctranslate2 CUDA support is the authoritative signal for
STT GPU availability — not torch.cuda.is_available(). torch may
be CPU-only on operator systems even when faster-whisper can run
on GPU via ctranslate2's own CUDA build.
"""
from __future__ import annotations

import unittest


class CtranslateCudaProbeTest(unittest.TestCase):
    """These tests document the contract that ctranslate2 is the
    source of truth for GPU availability in this project's STT
    pipeline. Tests don't REQUIRE CUDA to pass — they SKIP cleanly
    on systems without it."""

    def test_ctranslate2_importable(self) -> None:
        try:
            import ctranslate2
        except ImportError:
            self.skipTest("ctranslate2 not installed")
        self.assertTrue(hasattr(ctranslate2, "get_cuda_device_count"))

    def test_ctranslate2_cuda_count_is_int(self) -> None:
        try:
            import ctranslate2
        except ImportError:
            self.skipTest("ctranslate2 not installed")
        count = ctranslate2.get_cuda_device_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_faster_whisper_gpu_inference_works(self) -> None:
        """End-to-end probe: load tiny model on cuda, transcribe
        1s of audio. SKIPS if no CUDA device, FAILS if device
        present but inference raises (the Q.0 bug)."""
        try:
            import ctranslate2
            from faster_whisper import WhisperModel
            import numpy as np
        except ImportError as exc:
            self.skipTest(f"deps missing: {exc}")
        if ctranslate2.get_cuda_device_count() < 1:
            self.skipTest("no CUDA device detected")
        m = WhisperModel("tiny", device="cuda", compute_type="float16")
        audio = (np.random.randn(16000) * 100).astype(np.float32) / 32768
        try:
            segs, _ = m.transcribe(audio, language="es", beam_size=1)
            list(segs)  # force generator
        except RuntimeError as exc:
            # The Q.0 bug: "cublas64_12.dll not found" or similar
            # runtime DLL missing. Fail explicitly with the
            # actionable hint.
            self.fail(
                f"GPU inference failed despite CUDA device present.\n"
                f"  Error: {exc}\n"
                f"  Fix: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12\n"
                f"  See: docs/architecture/sprint_prompts/sprint_hotfix_2026_05_17_q0.md"
            )


if __name__ == "__main__":
    unittest.main()
```

### Q.0.8 — Commit

`chore(env): restore CUDA runtime for faster-whisper inference`

Mensaje:

```
chore(env): restore CUDA runtime for faster-whisper inference

Sprint S surfaced that stt_latency_p95 is SKIPPED because
faster-whisper inference fails on GPU with:
  RuntimeError: Library cublas64_12.dll is not found or cannot be loaded

Diagnosis: operator has NVIDIA driver 596.36 + CUDA 13 toolkit
installed (cublas64_13.dll present). But ctranslate2 4.7.1
(faster-whisper's backend) was compiled against CUDA 12 and
searches for cublas64_12.dll specifically. Version mismatch.

Note that torch is also CPU-only on this system (2.10.0+cpu) —
which is fine for our purposes; we don't need torch on GPU
(Silero VAD runs fine on CPU). The fix is specifically for
ctranslate2/faster-whisper.

Fix: install nvidia-cublas-cu12 + nvidia-cudnn-cu12 from PyPI.
These are official NVIDIA wheels that ship the CUDA 12 runtime
DLLs that ctranslate2 expects. They land in
site-packages/nvidia/cublas/bin/ which ctranslate2 finds
automatically.

Validation:
- ctranslate2.get_cuda_device_count() returns >= 1.
- faster-whisper end-to-end probe (tiny model, 1s audio,
  device='cuda', compute_type='float16') transcribes without
  RuntimeError.
- scripts/bench.py stt_latency_p95 now measures (PASS or FAIL
  numeric, not SKIPPED).

Also: scripts/bench.py::measure_stt_latency_p95 was checking
torch.cuda.is_available() — wrong source of truth for our
pipeline. Updated to check ctranslate2.get_cuda_device_count()
+ run an actual inference probe before declaring CUDA usable.

Tests: test_cuda_availability.py documents the
"ctranslate2-is-authoritative" contract. Tests SKIP cleanly on
systems without CUDA; FAIL with actionable hint on systems with
CUDA but missing runtime DLLs (the Q.0 bug).

requirements.txt gains nvidia-cublas-cu12 and nvidia-cudnn-cu12
as explicit deps so future fresh installs work without manual
intervention.

Tilde-file cleanup of ~orch/~rch/~1rch/~=rch in site-packages
(pip install leftovers) — unrelated to the fix but tidies the
environment.
```

---

## REPORTE FINAL

Devolveme:

1. Hash del commit.
2. Output del probe end-to-end manual:
   ```bash
   python -c "
   import ctranslate2
   print('cuda devices:', ctranslate2.get_cuda_device_count())
   from faster_whisper import WhisperModel
   import numpy as np
   m = WhisperModel('small', device='cuda', compute_type='float16')
   audio = (np.random.randn(16000 * 2) * 2000).astype(np.float32) / 32768
   import time; t0 = time.time()
   segs, _ = m.transcribe(audio, language='es', beam_size=5)
   list(segs)
   print(f'2s clip in {time.time() - t0:.2f}s on GPU')
   "
   ```
   Esperás algo como:
   ```
   cuda devices: 1
   Loaded on cuda/float16 in X.Xs
   2s clip in 0.X s on GPU
   ```
3. Output de `python -m pytest gemma4_agent/test_cuda_availability.py -v`.
4. Output de `python -m pytest gemma4_agent/ -q --tb=line`
   (suite completa, no regresa).
5. **Re-corrida del bench post-fix**:
   ```bash
   python scripts/bench.py
   ```
   Pegame:
   - El output completo del console.
   - El JSON nuevo de `bench_results/`.
   - Confirmación de que `stt_latency_p95` ya NO está SKIPPED
     — debe mostrar PASS o FAIL con número.
6. Cuál de las 3 soluciones funcionó (Q.0.1 / Q.0.2 / Q.0.3).
7. Si la limpieza de tilde files se hizo, qué se borró.

## CRITERIO DE ÉXITO

- 1 commit aterrizado.
- `python -c "from faster_whisper import WhisperModel; m = WhisperModel('tiny', device='cuda', compute_type='float16'); ..."` corre sin RuntimeError.
- `python scripts/bench.py` ahora mide `stt_latency_p95` con un
  número (PASS o FAIL — no SKIPPED).
- ≥3 tests nuevos verdes (1 puede SKIP si CUDA está ausente en
  CI).
- Suite completa verde.
- `requirements.txt` actualizado con `nvidia-cublas-cu12` y
  `nvidia-cudnn-cu12`.

## NO HACER (anti-scope)

- NO reinstales torch con CUDA. Es 2GB de download y rompe
  xformers/transformers que podrían depender de la build CPU.
  Si después de Q.0 querés torch-GPU para otra cosa, eso es un
  sprint dedicado con verificación de compat.
- NO toques CUDA toolkit. El operador tiene 13.0 instalado —
  funciona. El problema es ctranslate2 buscando 12, no que 13
  esté mal.
- NO toques voice pipeline ni router ni nada del runtime real.
- NO bypasses el problema haciendo el bench skipear con razón
  diferente. Si CUDA inference NO funciona después de las 3
  soluciones, reportá honesto y dejá `stt_latency_p95` SKIPPED
  con razón específica para que el operador pueda actuar
  manual.
- NO commitees DLLs al repo. Si Q.0.2 (copia manual) es la
  solución que funcionó, agregar el comando a un script
  `scripts/setup_cuda_runtime.py` y commitear ESE — no los
  binarios.
- Si Q.0.1 funciona (preferida), NO ejecutes Q.0.2 ni Q.0.3.
  La primera que funciona es la elegida.

## Follow-ups documentados

1. **Cuando aparezca el operator-recorded `testaudio_v2.wav`**:
   re-correr `scripts/testaudio_groundtruth.py` con GPU
   (5min vs 8.5min CPU). Y re-correr bench para actualizar el
   `stt_wer_mean` baseline contra audio nativo.

2. **`stt_latency_p95` puede FAIL en RTX modesta**: si el
   measured viene 1.5-2.0s en lugar de <1.2s, ese es el dato
   real para decidir Sprint Q (model upgrade). No es bug —
   es información.

3. **Si en algún momento se reinstala torch con CUDA**: revisar
   que `bench.py::measure_stt_latency_p95` siga usando
   ctranslate2 como check, no torch — son sistemas independientes
   y torch puede estar disponible pero ctranslate2 broken o
   viceversa.

4. **Auto-detección de CUDA mismatch**: feature futura. Si en
   un futuro NVIDIA releases CUDA 14 y ctranslate2 sigue
   compilado contra 12, el operador volverá a tener el mismo
   bug. Un sprint chico podría agregar al `launcher status` una
   línea "ctranslate2 expects CUDA X.X, system has Y.Y, install
   nvidia-cublas-cuX from pypi".
