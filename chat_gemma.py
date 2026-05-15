"""Chat interactivo con Gemma 4 E4B-Q6_K.

Asume que llama-server CUDA esta levantado en localhost:8080. Si no lo esta,
te avisa con el comando exacto para levantarlo.

Uso:
    python chat_gemma.py            # chat texto
    python chat_gemma.py --image foo.png   # chat con imagen
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# UTF-8 stdout para Windows
if hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SERVER = "http://127.0.0.1:8080"
HEALTH = f"{SERVER}/health"
CHAT = f"{SERVER}/v1/chat/completions"

# Sampling oficial Gemma 4
SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "repeat_penalty": 1.0,
    "max_tokens": 1024,
}

# System prompt simple para chat conversacional
SYSTEM_PROMPT = """Sos Gemma 4, un asistente local en español rioplatense. Respondé natural, breve y útil.
Si te muestran una imagen, describila o respondé preguntas sobre ella.
Si te piden hacer algo que no podés (sin tools), explicalo honestamente."""

PALETTE = {
    "user": "\033[33;1m",   # amarillo
    "assistant": "\033[36m", # cyan
    "system": "\033[90m",    # gris
    "error": "\033[31;1m",   # rojo
    "ok": "\033[32m",        # verde
    "reset": "\033[0m",
}


def enable_ansi():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def server_alive() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def server_help():
    print(f"{PALETTE['error']}llama-server no responde en {SERVER}{PALETTE['reset']}")
    print(f"\n{PALETTE['system']}Levantalo con este comando en otra PowerShell:{PALETTE['reset']}\n")
    print('  & "C:\\llamacpp-cuda\\bin\\llama-server.exe" `')
    print('      -m "C:\\Users\\usuario\\Desktop\\ETC\\Programacion\\Probando Gemma 4\\models\\E4B\\gemma-4-E4B-it-Q6_K.gguf" `')
    print('      --mmproj "C:\\Users\\usuario\\Desktop\\ETC\\Programacion\\Probando Gemma 4\\models\\E4B\\mmproj-F16.gguf" `')
    print('      --jinja --port 8080 -ngl 99 -c 16384 `')
    print('      --parallel 1 --ctx-checkpoints 1 --flash-attn on')
    print(f"\n{PALETTE['system']}Esperá ~10s a que termine de cargar el modelo,")
    print(f"hasta ver 'server is listening on http://127.0.0.1:8080'.{PALETTE['reset']}\n")
    print(f"Despues volve a correr {PALETTE['ok']}python chat_gemma.py{PALETTE['reset']}\n")


def encode_image(path: Path) -> str:
    """Devuelve data URI base64 de la imagen."""
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{ext};base64,{b64}"


def stream_chat(messages: list[dict], image_path: Path | None = None) -> str:
    """POST a /v1/chat/completions con stream. Imprime live. Devuelve respuesta completa."""
    # Preparar el ultimo user message con imagen si corresponde
    if image_path and messages[-1]["role"] == "user" and not isinstance(messages[-1]["content"], list):
        text = messages[-1]["content"]
        messages[-1]["content"] = [
            {"type": "image_url", "image_url": {"url": encode_image(image_path)}},
            {"type": "text", "text": text},
        ]

    body = {
        "messages": messages,
        "stream": True,
        **SAMPLING,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        CHAT, data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )

    full = []
    t0 = time.monotonic()
    first_token_t = None

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    if first_token_t is None:
                        first_token_t = time.monotonic()
                    full.append(content)
                    print(content, end="", flush=True)
    except urllib.error.URLError as e:
        print(f"\n{PALETTE['error']}Error de conexion: {e}{PALETTE['reset']}")
        return ""
    except Exception as e:
        print(f"\n{PALETTE['error']}Error: {type(e).__name__}: {e}{PALETTE['reset']}")
        return ""

    elapsed = time.monotonic() - t0
    ttft = (first_token_t - t0) if first_token_t else 0
    text = "".join(full)
    print(f"\n{PALETTE['system']}[{elapsed:.2f}s total, {ttft:.2f}s primer token, {len(text)} chars]{PALETTE['reset']}")
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Ruta a imagen para enviar en el primer turno")
    parser.add_argument("--no-system", action="store_true", help="No mandar system prompt")
    args = parser.parse_args()

    enable_ansi()

    if not server_alive():
        server_help()
        sys.exit(2)

    print(f"{PALETTE['ok']}Conectado a Gemma 4 E4B-Q6_K en {SERVER}{PALETTE['reset']}")
    print(f"{PALETTE['system']}Comandos: /quit (salir), /clear (limpiar conversacion), /image <path> (cargar imagen){PALETTE['reset']}\n")

    messages: list[dict] = []
    if not args.no_system:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

    pending_image: Path | None = Path(args.image) if args.image else None
    if pending_image and not pending_image.exists():
        print(f"{PALETTE['error']}Imagen no encontrada: {pending_image}{PALETTE['reset']}")
        pending_image = None
    elif pending_image:
        print(f"{PALETTE['system']}Imagen cargada: {pending_image} (se enviara en el primer mensaje){PALETTE['reset']}\n")

    while True:
        try:
            user = input(f"{PALETTE['user']}vos>{PALETTE['reset']} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user:
            continue

        if user.lower() in ("/quit", "/exit", "/q"):
            break
        if user.lower() == "/clear":
            messages = ([messages[0]] if messages and messages[0]["role"] == "system" else [])
            pending_image = None
            print(f"{PALETTE['system']}Conversacion limpiada.{PALETTE['reset']}\n")
            continue
        if user.lower().startswith("/image "):
            path = Path(user[7:].strip().strip('"').strip("'"))
            if not path.exists():
                print(f"{PALETTE['error']}No existe: {path}{PALETTE['reset']}\n")
            else:
                pending_image = path
                print(f"{PALETTE['system']}Imagen cargada: {path}. Escribi tu pregunta sobre ella.{PALETTE['reset']}\n")
            continue

        messages.append({"role": "user", "content": user})

        print(f"{PALETTE['assistant']}gemma>{PALETTE['reset']} ", end="", flush=True)
        reply = stream_chat(messages, image_path=pending_image)
        pending_image = None  # solo se manda una vez

        if reply:
            messages.append({"role": "assistant", "content": reply})
        print()

    print(f"\n{PALETTE['system']}chau.{PALETTE['reset']}")


if __name__ == "__main__":
    main()
