"""Block D — audio multimodal via llama-mtmd-cli subprocess.

llama-server does NOT route input_audio for Gemma 4 yet (issue ggml-org/llama.cpp#21868).
Workaround: spawn llama-mtmd-cli per audio file. Cold-loads model each call (slow).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

LLAMA_MTMD_CLI = r"C:\Users\usuario\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-mtmd-cli.exe"
ROOT = Path(__file__).parent.parent

SAMPLES = [
    {"id": "audio_01", "file": "samples/audio_01_hora.wav",
     "transcript_expected": "qué hora es",
     "intent": "tool: system_time"},
    {"id": "audio_02", "file": "samples/audio_02_negation.wav",
     "transcript_expected": "no abras Spotify, solo decime si está instalado",
     "intent": "tool: list_apps. NEVER app_open."},
    {"id": "audio_03", "file": "samples/audio_03_multistep.wav",
     "transcript_expected": "abrí Notepad y escribí hola mundo",
     "intent": "tool: app_open + type_text"},
    {"id": "audio_04", "file": "samples/audio_04_phonetic.wav",
     "transcript_expected": "abrí stim (Steam mispronounced)",
     "intent": "tool: app_open(steam.exe). Tolerate mispronunciation."},
    {"id": "audio_05", "file": "samples/audio_05_codeswitch.wav",
     "transcript_expected": "dame el time y abrí Spotify por favor",
     "intent": "tool: system_time + app_open(spotify)"},
]


def run_one(model_path, mmproj, audio_path, prompt):
    """Spawns llama-mtmd-cli with one audio + prompt; returns (stdout, latency)."""
    cmd = [
        LLAMA_MTMD_CLI,
        "-m", model_path,
        "--mmproj", mmproj,
        "--audio", audio_path,
        "-p", prompt,
        "-ngl", "99",
        "-c", "4096",
        "--temp", "0.7",
        "-n", "256",
        "--no-display-prompt",
    ]
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
        elapsed = time.time() - t0
        return result.stdout, result.stderr, elapsed, result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT after 300s", time.time() - t0, -1


def main():
    if len(sys.argv) < 3:
        print("usage: audio_probes.py <model_gguf> <mmproj_gguf> [model_label]")
        sys.exit(1)
    model_path = sys.argv[1]
    mmproj = sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else Path(model_path).stem

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"audio_{label}.json"

    results = {"model": label, "model_path": model_path, "mmproj": mmproj, "samples": []}

    # Two passes per audio: (1) raw transcription, (2) intent — does it pick the right tool concept?
    for s in SAMPLES:
        audio_full = str(ROOT / s["file"])
        print(f"\n[{label}] {s['id']}: {s['transcript_expected']}", flush=True)

        # Pass 1: transcribe
        prompt_t = "Transcribe el audio anterior en español. Devuelve solo la transcripción exacta, sin explicaciones."
        stdout_t, stderr_t, lat_t, rc_t = run_one(model_path, mmproj, audio_full, prompt_t)
        print(f"  transcription ({lat_t:.1f}s, rc={rc_t}): {stdout_t[:200].strip()}", flush=True)

        # Pass 2: intent — what would you do?
        prompt_i = "Escucha este audio. ¿Qué herramienta debería llamar el asistente y con qué argumentos? Responde brevemente."
        stdout_i, stderr_i, lat_i, rc_i = run_one(model_path, mmproj, audio_full, prompt_i)
        print(f"  intent ({lat_i:.1f}s, rc={rc_i}): {stdout_i[:200].strip()}", flush=True)

        results["samples"].append({
            "id": s["id"],
            "file": s["file"],
            "expected_transcript": s["transcript_expected"],
            "expected_intent": s["intent"],
            "transcription": {"text": stdout_t.strip(), "latency_s": round(lat_t, 2), "rc": rc_t, "stderr_tail": stderr_t[-500:] if stderr_t else ""},
            "intent": {"text": stdout_i.strip(), "latency_s": round(lat_i, 2), "rc": rc_i, "stderr_tail": stderr_i[-500:] if stderr_i else ""},
        })

    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
