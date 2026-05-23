"""Chat con Gemma 4 + tools REALES de Windows.

Diferencia con chat_gemma.py:
  - Aca el modelo tiene tools registradas y CUANDO LAS LLAMA, las ejecuta de verdad.
  - "abre Steam" -> realmente abre Steam.
  - "qué hora es" -> devuelve la hora real.
  - "lista archivos" -> lista la carpeta actual.

Tools implementadas (no son stubs):
  - system_time: hora real
  - system_volume: get/set volumen real (via nircmd o pycaw)
  - app_open: abre app real (start)
  - app_close: cierra app real (taskkill)
  - list_processes: tasklist real
  - list_windows: ventanas reales (powershell Get-Process)
  - filesystem_list: dir real
  - filesystem_read: lee archivo real
  - filesystem_write: escribe archivo real (sandbox/)
  - web_open_url: abre URL real en browser default
  - terminal_run: ejecuta comando real
  - clipboard_read/write: portapapeles real

Asume llama-server corriendo en :8080.
Uso:  python chat_carter.py
"""
from __future__ import annotations
import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SERVER = "http://127.0.0.1:8080"
HEALTH = f"{SERVER}/health"
CHAT = f"{SERVER}/v1/chat/completions"
SANDBOX = Path(__file__).parent / "sandbox_carter"
SANDBOX.mkdir(exist_ok=True)

SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "repeat_penalty": 1.0,
    "max_tokens": 1024,
}

PALETTE = {
    "user": "\033[33;1m", "assistant": "\033[36m",
    "tool": "\033[35m", "result": "\033[34m",
    "system": "\033[90m", "error": "\033[31;1m",
    "ok": "\033[32m", "reset": "\033[0m",
}


def enable_ansi():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


SYSTEM_PROMPT = """Sos Carter, un asistente local en Windows. Hablás español rioplatense, breve y útil.

REGLAS:
1. Cuando el usuario pida una acción que necesita una tool, USÁ la tool. No digas "soy una IA, no puedo" — tenés tools reales.
2. Para acciones DESTRUCTIVAS (delete, format, shutdown, install, kill, comprar) PEDÍ confirmación primero.
3. NO inventes resultados. Si la tool falla, decí qué pasó.
4. Después de llamar tools, respondé en una frase diciendo qué hiciste según el resultado real.
5. Si el usuario solo conversa, NO uses tools. Respondé natural.

EJEMPLOS:
- "abre Steam" → app_open(name="steam")
- "qué hora es" → system_time
- "lista archivos del sandbox" → filesystem_list(path="sandbox_carter")
- "abre YouTube" → web_open_url(url="https://www.youtube.com")
- "subi el volumen a 50" → system_set_volume(level=50)
- "borrá todos mis archivos" → "Eso es destructivo, ¿confirmás?" SIN tool
- "hola" → respondé natural sin tool"""


# ============================================================
# TOOLS REALES (Windows)
# ============================================================

def t_system_time(args):
    now = datetime.now()
    return {"ok": True, "iso": now.isoformat(), "human": now.strftime("%H:%M:%S del %d/%m/%Y")}


def t_system_get_volume(args):
    """Lee volumen via PowerShell + WMI."""
    try:
        # Usa pycaw si está, sino fallback a powershell
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            level = int(volume.GetMasterVolumeLevelScalar() * 100)
            muted = bool(volume.GetMute())
            return {"ok": True, "level": level, "muted": muted}
        except ImportError:
            return {"ok": False, "error": "pycaw no instalado. pip install pycaw comtypes"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def t_system_set_volume(args):
    level = int(args.get("level", 50))
    level = max(0, min(100, level))
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        # Verificar
        new_level = int(volume.GetMasterVolumeLevelScalar() * 100)
        return {"ok": True, "level": new_level, "verified": new_level == level}
    except ImportError:
        return {"ok": False, "error": "pycaw no instalado. pip install pycaw comtypes"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def t_system_mute(args):
    state = bool(args.get("state", True))
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(int(state), None)
        new_state = bool(volume.GetMute())
        return {"ok": True, "muted": new_state, "verified": new_state == state}
    except ImportError:
        return {"ok": False, "error": "pycaw no instalado"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Mapping nombre amigable -> exe / URI
APP_ALIASES = {
    "notepad": "notepad.exe",
    "calc": "calc.exe", "calculadora": "calc.exe",
    "explorer": "explorer.exe", "explorador": "explorer.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "spotify": "spotify",       # via shell:appsfolder o protocol
    "steam": "steam://open/main",
    "discord": "discord.exe",
    "vscode": "code.cmd", "code": "code.cmd",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe", "powershell": "powershell.exe",
}


def t_app_open(args):
    name = (args.get("name") or "").strip().lower()
    if not name:
        return {"ok": False, "error": "name vacio"}
    target = APP_ALIASES.get(name, name)
    try:
        # Si es URI scheme (steam://), abrir como URL
        if "://" in target:
            os.startfile(target)
            return {"ok": True, "name": name, "method": "uri", "target": target}
        # Sino, ejecutar como proceso
        subprocess.Popen(target, shell=True)
        return {"ok": True, "name": name, "method": "shell", "target": target}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def t_app_close(args):
    name = (args.get("name") or "").strip().lower()
    if not name:
        return {"ok": False, "error": "name vacio"}
    exe = APP_ALIASES.get(name, name)
    if not exe.endswith(".exe"):
        exe = exe + ".exe"
    try:
        result = subprocess.run(["taskkill", "/IM", exe, "/F"],
                                capture_output=True, text=True, timeout=10)
        return {"ok": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_list_processes(args):
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                                capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().splitlines()[:30]
        procs = []
        for line in lines:
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) >= 2:
                procs.append({"name": parts[0].lstrip('"'), "pid": parts[1]})
        return {"ok": True, "processes": procs[:20], "total_shown": len(procs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_list_windows(args):
    try:
        ps = "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object -First 15 ProcessName, MainWindowTitle, Id | ConvertTo-Json"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        windows = [{"title": d.get("MainWindowTitle"), "process": d.get("ProcessName"), "pid": d.get("Id")} for d in data]
        return {"ok": True, "windows": windows}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_filesystem_list(args):
    path = args.get("path", ".").strip() or "."
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"path no existe: {path}"}
    try:
        items = []
        for entry in sorted(p.iterdir())[:50]:
            items.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return {"ok": True, "path": str(p.absolute()), "items": items, "total": len(items)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_filesystem_read(args):
    path = args.get("path", "").strip()
    if not path:
        return {"ok": False, "error": "path vacio"}
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": f"file no existe: {path}"}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "path": str(p.absolute()),
                "content": content[:2000],
                "truncated": len(content) > 2000,
                "size_bytes": p.stat().st_size}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_filesystem_write(args):
    """Solo escribe en sandbox_carter/ por seguridad."""
    rel_path = args.get("path", "").strip().lstrip("/").lstrip("\\")
    content = args.get("content", "")
    if not rel_path:
        return {"ok": False, "error": "path vacio"}
    full = (SANDBOX / rel_path).resolve()
    # Anti escape de sandbox
    if SANDBOX.resolve() not in full.parents and full != SANDBOX.resolve():
        return {"ok": False, "error": f"escape de sandbox bloqueado: {rel_path}"}
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(full), "bytes": len(content.encode("utf-8"))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_web_open_url(args):
    url = args.get("url", "").strip()
    if not url:
        return {"ok": False, "error": "url vacia"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return {"ok": True, "url": url, "browser": "default"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_terminal_run(args):
    """Ejecuta comando arbitrario. ATENCION: poderoso. Sin sandbox."""
    cmd = args.get("command", "").strip()
    cmd_args = args.get("args", [])
    if not cmd:
        return {"ok": False, "error": "command vacio"}
    full_cmd = [cmd] + (cmd_args if isinstance(cmd_args, list) else [str(cmd_args)])
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True,
                                timeout=30, shell=True)
        return {"ok": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout.strip()[:1500],
                "stderr": result.stderr.strip()[:500]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout 30s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_clipboard_read(args):
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                                capture_output=True, text=True, timeout=5)
        return {"ok": True, "content": result.stdout.strip()[:2000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def t_clipboard_write(args):
    text = args.get("content", "")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value @'\n{text}\n'@"],
                       check=True, timeout=5)
        return {"ok": True, "wrote_chars": len(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


TOOL_IMPLS = {
    "system_time": t_system_time,
    "system_get_volume": t_system_get_volume,
    "system_set_volume": t_system_set_volume,
    "system_mute": t_system_mute,
    "app_open": t_app_open,
    "app_close": t_app_close,
    "list_processes": t_list_processes,
    "list_windows": t_list_windows,
    "filesystem_list": t_filesystem_list,
    "filesystem_read": t_filesystem_read,
    "filesystem_write": t_filesystem_write,
    "web_open_url": t_web_open_url,
    "terminal_run": t_terminal_run,
    "clipboard_read": t_clipboard_read,
    "clipboard_write": t_clipboard_write,
}


# ============================================================
# TOOL SCHEMAS (formato OpenAI)
# ============================================================

TOOLS = [
    {"type": "function", "function": {
        "name": "system_time",
        "description": "Devuelve la hora actual del sistema.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "system_get_volume",
        "description": "Lee el volumen actual del sistema (0-100) y estado mute.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "system_set_volume",
        "description": "Ajusta el volumen master del sistema. level: 0-100.",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer", "minimum": 0, "maximum": 100}
        }, "required": ["level"]},
    }},
    {"type": "function", "function": {
        "name": "system_mute",
        "description": "Mutea o desmutea el sistema. state: true=mute, false=unmute.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "boolean"}
        }, "required": ["state"]},
    }},
    {"type": "function", "function": {
        "name": "app_open",
        "description": "Abre una aplicacion por nombre. Soporta: notepad, calc, explorer, chrome, edge, spotify, steam, discord, vscode, paint, cmd, powershell. Tambien acepta cualquier .exe en PATH.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Nombre amigable o exe (ej: notepad, steam, calc)"}
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "app_close",
        "description": "Cierra una aplicacion forzosamente (taskkill /F).",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "list_processes",
        "description": "Lista procesos activos del sistema (top 20).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "list_windows",
        "description": "Lista ventanas abiertas con sus titulos.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "filesystem_list",
        "description": "Lista archivos y carpetas en una ruta. Por defecto: cwd.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Ruta a listar"}
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "filesystem_read",
        "description": "Lee contenido de archivo de texto.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "filesystem_write",
        "description": "Escribe archivo en sandbox_carter/. Path es relativo a sandbox.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "web_open_url",
        "description": "Abre URL en navegador default.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}
        }, "required": ["url"]},
    }},
    {"type": "function", "function": {
        "name": "terminal_run",
        "description": "Ejecuta comando en terminal. Solo para comandos seguros (echo, dir, python --version, git status, etc). Para acciones destructivas pedi confirmacion primero.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}}
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "clipboard_read",
        "description": "Lee el contenido actual del portapapeles.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "clipboard_write",
        "description": "Copia texto al portapapeles.",
        "parameters": {"type": "object", "properties": {
            "content": {"type": "string"}
        }, "required": ["content"]},
    }},
]


# ============================================================
# CLIENT
# ============================================================

def server_alive():
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def chat_call(messages):
    """No-stream para que sea facil parsear tool_calls."""
    body = {"messages": messages, "tools": TOOLS, "tool_choice": "auto", **SAMPLING}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(CHAT, data=data,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def execute_tool(name, args):
    impl = TOOL_IMPLS.get(name)
    if not impl:
        return {"ok": False, "error": f"tool no implementada: {name}"}
    try:
        return impl(args)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


MAX_TURNS = 5


def run_user_turn(messages, user_input):
    messages.append({"role": "user", "content": user_input})

    for turn in range(MAX_TURNS):
        t0 = time.monotonic()
        try:
            resp = chat_call(messages)
        except Exception as e:
            print(f"{PALETTE['error']}LLM error: {e}{PALETTE['reset']}")
            return
        elapsed = time.monotonic() - t0

        choice = resp["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            # Respuesta final
            if content:
                print(f"{PALETTE['assistant']}gemma>{PALETTE['reset']} {content}")
            else:
                print(f"{PALETTE['error']}(reply vacio){PALETTE['reset']}")
            print(f"{PALETTE['system']}[{elapsed:.2f}s]{PALETTE['reset']}\n")
            messages.append({"role": "assistant", "content": content})
            return

        # Hay tool calls — mostrarlos y ejecutarlos
        if content:
            print(f"{PALETTE['assistant']}gemma>{PALETTE['reset']} {content}")

        # Append assistant message con tool_calls
        messages.append({
            "role": "assistant", "content": content,
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "?")
            args = parse_args(fn.get("arguments", {}))
            args_str = json.dumps(args, ensure_ascii=False)
            if len(args_str) > 100:
                args_str = args_str[:97] + "..."
            print(f"{PALETTE['tool']}  -> {name}({args_str}){PALETTE['reset']}")

            t_start = time.monotonic()
            result = execute_tool(name, args)
            t_tool = time.monotonic() - t_start

            result_str = json.dumps(result, ensure_ascii=False)
            short = result_str if len(result_str) <= 200 else result_str[:197] + "..."
            color = PALETTE['result'] if result.get("ok") else PALETTE['error']
            print(f"{color}     <- {short}  [{t_tool*1000:.0f}ms]{PALETTE['reset']}")

            messages.append({
                "role": "tool", "tool_call_id": tc.get("id", f"call_{name}"),
                "content": result_str,
            })

    print(f"{PALETTE['error']}(loop sin reply final tras {MAX_TURNS} turns){PALETTE['reset']}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-system", action="store_true")
    args = parser.parse_args()

    enable_ansi()

    if not server_alive():
        print(f"{PALETTE['error']}llama-server no responde en {SERVER}{PALETTE['reset']}")
        print(f"{PALETTE['system']}Levantalo con:")
        print('  & "C:\\llamacpp-cuda\\bin\\llama-server.exe" -m models\\E4B\\gemma-4-E4B-it-Q6_K.gguf --mmproj models\\E4B\\mmproj-F16.gguf --jinja --port 8080 -ngl 99 -c 16384 --parallel 1 --ctx-checkpoints 1 --flash-attn on')
        print(PALETTE['reset'])
        sys.exit(2)

    print(f"{PALETTE['ok']}Carter live en {SERVER}{PALETTE['reset']}")
    print(f"{PALETTE['system']}Tools reales activas: {len(TOOL_IMPLS)} | Sandbox: {SANDBOX}")
    print(f"Comandos: /quit /clear{PALETTE['reset']}")
    print(f"{PALETTE['system']}Probá: 'qué hora es', 'abrí Notepad', 'lista procesos', 'subi volumen a 30', etc.{PALETTE['reset']}\n")

    messages = []
    if not args.no_system:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

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
            print(f"{PALETTE['system']}Limpiado.{PALETTE['reset']}\n")
            continue
        run_user_turn(messages, user)

    print(f"{PALETTE['system']}chau{PALETTE['reset']}")


if __name__ == "__main__":
    main()
