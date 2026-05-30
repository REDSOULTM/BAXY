"""¿Parakeet carga de verdad, o el pipeline cae al fallback Whisper (peor)?
Replica la lógica de VoicePipeline._build_stt + load() y reporta el motor REAL."""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 1) ¿está sherpa-onnx?
try:
    import sherpa_onnx
    print(f"[sherpa-onnx] OK  version={getattr(sherpa_onnx, '__version__', '?')}")
except Exception as e:
    print(f"[sherpa-onnx] IMPORT FAIL: {type(e).__name__}: {e}")

# 2) ¿carga ParakeetSTT?
try:
    from gemma4_agent.voice.parakeet_stt import ParakeetSTT
    pk = ParakeetSTT()
    # mostrar de dónde saca el modelo si está accesible
    for attr in ("_model_dir", "model_dir", "_encoder", "_decoder", "_joiner", "_tokens", "_model_path"):
        v = getattr(pk, attr, None)
        if v:
            print(f"   ParakeetSTT.{attr} = {v}")
    ok = pk.load()
    print(f"[ParakeetSTT.load] {'OK ✓' if ok else 'FAIL ✗'}  last_error={getattr(pk, 'last_error', None)!r}")
except Exception as e:
    import traceback
    print(f"[ParakeetSTT] EXC: {type(e).__name__}: {e}")
    traceback.print_exc()

# 3) ¿qué motor elegiría el pipeline REAL (con su fallback)?
try:
    from gemma4_agent.voice.pipeline import VoicePipeline
    eng = VoicePipeline._build_stt("parakeet")
    print(f"[pipeline._build_stt('parakeet')] -> {type(eng).__name__}")
    loaded = eng.load()
    if not loaded and type(eng).__name__ != "STT":
        print("   -> Parakeet NO cargó; el pipeline caería a Whisper (fallback).")
    print(f"   load()={loaded}  last_error={getattr(eng, 'last_error', None)!r}")
except Exception as e:
    print(f"[pipeline] EXC: {type(e).__name__}: {e}")
