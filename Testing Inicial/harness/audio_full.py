"""Full Block D: probe 5 wavs against
(1) Ollama gemma4:e4b OpenAI-compat /v1 input_audio (production-ready path)
(2) llama-mtmd-cli with E4B-Q5_K_M (local llama.cpp path, cold-load)

Outputs results/audio_E4B.json with both transcriptions side-by-side.
"""
import base64
import json
import subprocess
import time
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).parent.parent
RESULTS = ROOT / "results"
SAMPLES = [
    {"id": "audio_01", "file": "samples/audio_01_hora.wav",
     "expected": "qué hora es",
     "intent": "tool: system_time"},
    {"id": "audio_02", "file": "samples/audio_02_negation.wav",
     "expected": "no abras Spotify, solo decime si está instalado",
     "intent": "tool: list_apps. NEVER app_open."},
    {"id": "audio_03", "file": "samples/audio_03_multistep.wav",
     "expected": "abrí Notepad y escribí hola mundo",
     "intent": "tool: app_open + type_text"},
    {"id": "audio_04", "file": "samples/audio_04_phonetic.wav",
     "expected": "abrí stim (Steam mispronounced)",
     "intent": "tool: app_open(steam.exe)"},
    {"id": "audio_05", "file": "samples/audio_05_codeswitch.wav",
     "expected": "dame el time y abrí Spotify por favor",
     "intent": "tool: system_time + app_open(spotify)"},
]

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
OLLAMA_MODEL = "gemma4:e4b"

LLAMA_MTMD = r"C:\llamacpp-cuda\bin\llama-mtmd-cli.exe"
GGUF = ROOT / "models" / "E4B" / "gemma-4-E4B-it-Q5_K_M.gguf"
MMPROJ = ROOT / "models" / "E4B" / "mmproj-F16.gguf"


def call_ollama(audio_b64, prompt):
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": [
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
            {"type": "text", "text": prompt},
        ]}],
    }
    data = json.dumps(body).encode("utf-8")
    req = urlrequest.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urlrequest.urlopen(req, timeout=300) as r:
            elapsed = time.time() - t0
            d = json.loads(r.read())
            text = d["choices"][0]["message"]["content"]
            return {"text": text, "latency_s": round(elapsed, 2), "ok": True, "raw": None}
    except Exception as e:
        return {"text": "", "latency_s": round(time.time() - t0, 2), "ok": False, "raw": f"{type(e).__name__}: {e}"}


def call_mtmd_cli(audio_path, prompt):
    cmd = [LLAMA_MTMD, "-m", str(GGUF), "--mmproj", str(MMPROJ),
           "--audio", str(audio_path), "-p", prompt, "-ngl", "99",
           "-c", "4096", "-n", "256", "--temp", "0.7"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
        return {"text": r.stdout.strip(), "latency_s": round(time.time() - t0, 2),
                "ok": r.returncode == 0, "rc": r.returncode,
                "stderr_tail": (r.stderr or "")[-300:]}
    except subprocess.TimeoutExpired:
        return {"text": "", "latency_s": round(time.time() - t0, 2), "ok": False, "raw": "TIMEOUT"}


def main():
    results = {"runs": []}
    for s in SAMPLES:
        wav_path = ROOT / s["file"]
        audio_b64 = base64.b64encode(wav_path.read_bytes()).decode("ascii")

        print(f"\n=== {s['id']}: {s['expected']} ===")

        for prompt_label, prompt in [("transcription", "Transcribe el audio en español. Devuelve solo la transcripción."),
                                      ("intent", "Escucha el audio. ¿Qué herramienta llamarías y con qué argumentos? Responde brevemente.")]:
            print(f"  [{prompt_label}] OLLAMA...", end=" ", flush=True)
            ollama = call_ollama(audio_b64, prompt)
            print(f"{ollama['latency_s']}s -> {ollama['text'][:100]}")

            print(f"  [{prompt_label}] MTMD-CLI...", end=" ", flush=True)
            mtmd = call_mtmd_cli(wav_path, prompt)
            print(f"{mtmd['latency_s']}s -> {mtmd['text'][:100]}")

            results["runs"].append({
                "sample_id": s["id"],
                "expected": s["expected"],
                "intent_expected": s["intent"],
                "prompt_label": prompt_label,
                "prompt": prompt,
                "ollama": ollama,
                "mtmd_cli": mtmd,
            })

    out = RESULTS / "audio_E4B.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
