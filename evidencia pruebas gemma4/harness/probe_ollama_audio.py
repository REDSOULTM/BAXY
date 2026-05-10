"""Probe whether Ollama HTTP API actually accepts audio input for Gemma 4.

Tries both /api/chat (Ollama native) and /v1/chat/completions (OpenAI-compat)
with several plausible field names. Reports what works.
"""
import base64
import json
from pathlib import Path
from urllib import request as urlrequest, error as urlerror

ROOT = Path(__file__).parent.parent
WAV = ROOT / "samples" / "audio_01_hora.wav"
MODEL = "gemma4:e4b"

def encode_wav():
    return base64.b64encode(WAV.read_bytes()).decode("ascii")

def post(url, body, timeout=120):
    data = json.dumps(body).encode("utf-8")
    req = urlrequest.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:600].decode("utf-8", errors="replace")
    except urlerror.HTTPError as e:
        return e.code, e.read()[:600].decode("utf-8", errors="replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"

def main():
    if not WAV.exists():
        print("missing wav"); return
    audio_b64 = encode_wav()
    print(f"audio b64 length: {len(audio_b64)}")
    print(f"model: {MODEL}\n")

    attempts = [
        # 1. Ollama native /api/chat with "audios" (analog to "images")
        {
            "label": "Ollama /api/chat with 'audios'",
            "url": "http://127.0.0.1:11434/api/chat",
            "body": {
                "model": MODEL,
                "stream": False,
                "messages": [
                    {"role": "user", "content": "Transcribe el audio.", "audios": [audio_b64]}
                ],
            },
        },
        # 2. Ollama native /api/chat with "audio"
        {
            "label": "Ollama /api/chat with 'audio'",
            "url": "http://127.0.0.1:11434/api/chat",
            "body": {
                "model": MODEL,
                "stream": False,
                "messages": [
                    {"role": "user", "content": "Transcribe el audio.", "audio": [audio_b64]}
                ],
            },
        },
        # 3. OpenAI-compat /v1/chat/completions with input_audio block
        {
            "label": "OpenAI-compat /v1 input_audio",
            "url": "http://127.0.0.1:11434/v1/chat/completions",
            "body": {
                "model": MODEL,
                "stream": False,
                "messages": [
                    {"role": "user", "content": [
                        {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
                        {"type": "text", "text": "Transcribe el audio."},
                    ]}
                ],
            },
        },
        # 4. /api/generate with "audios"
        {
            "label": "Ollama /api/generate with 'audios'",
            "url": "http://127.0.0.1:11434/api/generate",
            "body": {
                "model": MODEL,
                "stream": False,
                "prompt": "Transcribe el audio.",
                "audios": [audio_b64],
            },
        },
    ]

    for a in attempts:
        print(f"--- {a['label']} ---")
        code, body = post(a["url"], a["body"])
        print(f"HTTP {code}")
        print(body)
        print()

if __name__ == "__main__":
    main()
