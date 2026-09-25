"""F2 — the model «free»: the conversation as it is, the compact catalog, the owner's rules, schema-bound output.

No readers, no dialogue slot, no shortlist, no vetoes in front: one chat call per turn to a llama-server started
here with the product's binary and flags (1 slot, the context this prompt needs). The reply is mapped onto the
record shape scripts/comprension_eval.py scores (action/plan/clarify/conversation), so the same gold judges both.

usage: free_model.py --set S.jsonl --out RUN.jsonl [--gguf G] [--variant min|request] [--ctx 12288] [--limit N]
Writes RUN.jsonl (resumable) and RUN.meta.json (VRAM peak of the server tree, RAM, latency, prompt tokens).
"""
import argparse
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo")
sys.path.insert(0, str(REPO / "scripts"))
HERE = pathlib.Path(__file__).resolve().parent
MANIFEST = json.loads((pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "mind-runtime-v1.json").read_text())
CAPS = json.load(open(HERE / "catalog_config.json", encoding="utf-8"))["capabilities"]
OPS = sorted(c["name"] for c in CAPS)

FAMILY_TITLES = {
    "app": "aplicaciones", "audio": "sonido", "backup": "copias", "bluetooth": "bluetooth", "browser": "navegador",
    "calculator": "calculadora", "calendar": "agenda", "capture": "capturas", "clipboard": "portapapeles",
    "display": "pantalla", "email": "correo", "filesystem": "archivos", "game": "juegos", "input": "teclado y clics",
    "media": "música y video", "memory": "memoria privada", "message": "mensajes", "network": "red", "note": "notas",
    "notification": "alarmas y recordatorios", "ocr": "leer texto en pantalla", "office": "documentos",
    "package": "programas", "peripheral": "periféricos", "reminder": "recordatorios", "routine": "rutinas",
    "streaming": "streaming", "system": "sistema", "task": "tareas y listas", "vision": "describir la pantalla",
    "weather": "clima", "web": "web", "wifi": "wifi", "window": "ventanas",
}

POLICY = """Eres el decisor de BAXY, un asistente tipo Jarvis que vive en un PC con Windows. Lees la conversación y decides \
qué hacer con el ÚLTIMO mensaje de la persona. No ejecutas nada: sólo decides.

Decisiones posibles:
- "action": ejecutar una o varias operaciones del catálogo (lista abajo) que cubren lo pedido.
- "clarify": hacer UNA pregunta corta porque falta de verdad algo que cambia el resultado.
- "talk": contestar hablando, sin tocar el PC: conocimiento estable, charla, escribir contenido (código, recetas, \
listas, cuentos, traducciones), cálculos y conversiones, consejos, hablar de ti mismo, agradecer.
- "limit": decir en llano que eso no lo haces (no está en el catálogo).

Reglas:
1. Lo público se busca: lo que cambia o no se sabe de memoria con seguridad (clima, noticias, deportes, precios, dólar, \
horarios, estrenos, datos de una persona, empresa o lugar concretos, opiniones sobre una obra) → action con \
web.search (o weather.current para el clima, web.news.headlines para titulares). Lo estable (definiciones, cómo se \
hace algo, matemáticas, traducir, convertir unidades) → talk.
2. Lo propio no se busca en la web: datos de la persona (sus notas, recordatorios, alarmas, tareas, agenda, archivos, \
lo que suena en su PC), preguntas sobre ti o sobre lo que acabas de decir → la operación que lo lee, o talk, o clarify.
3. Lo completo no se repregunta: si el mensaje trae lo necesario, action. Un valor por defecto razonable (el clima de \
aquí, algo de música) no es una duda.
4. Cantidad relativa sin número («súbele un poco», «baja el brillo», «más fuerte») → clarify (cuánto). Con número o \
nivel → action.
5. Vives en un PC: no controlas luces ni aparatos de la casa, no haces llamadas ni SMS, no pides comida, taxis, \
compras ni reservas, no manejas el móvil ni relojes → limit (salvo que una operación del catálogo sirva de verdad).
6. Si falta un dato de la persona («¿llueve donde vive mi hermana?») → clarify.
7. Erratas, sin tildes, dictado sin puntuación y spanglish se entienden como la persona quiso decir.
8. Un mensaje que depende de lo anterior («¿y en Santiago?», «ahora en javascript», «20 minutos antes de eso», \
«súbele otro poco», «esa no, otra», «sí, dale», «10») se decide con la conversación: la misma operación con el valor \
nuevo, o talk que reusa lo que respondiste. Si acabas de preguntar algo y la persona contesta, completa ese pedido.
9. Charla, gracias, quejas y reacciones → talk.

Catálogo (operación: qué hace):
"""


def compact_catalog() -> str:
    families: dict[str, list[str]] = {}
    for cap in sorted(CAPS, key=lambda c: c["name"]):
        family = cap["name"].split(".", 1)[0]
        first = cap["description"].split(". ")[0].rstrip(".")
        families.setdefault(family, []).append(f"- {cap['name']}: {first[:140]}")
    return "\n".join(f"[{FAMILY_TITLES.get(f, f)}]\n" + "\n".join(lines) for f, lines in families.items())


def schema(variant: str) -> dict:
    properties: dict = {}
    if variant == "request":
        properties["request"] = {"type": "string", "maxLength": 200}
    properties["decision"] = {"type": "string", "enum": ["action", "clarify", "talk", "limit"]}
    properties["operations"] = {"type": "array", "items": {"type": "string", "enum": OPS}, "maxItems": 3}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


FORMAT_NOTE = {
    "min": "\nResponde sólo con JSON: {\"decision\": ..., \"operations\": [...]} (operations vacía si no es action).",
    "request": "\nResponde sólo con JSON: {\"request\": el último pedido reescrito como pedido completo y autónomo con "
               "lo que aporta la conversación, \"decision\": ..., \"operations\": [...]} (operations vacía si no es action).",
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(url: str, payload: dict, timeout: float = 120.0) -> dict:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def start_server(gguf: str, ctx: int, port: int) -> subprocess.Popen:
    command = [MANIFEST["llama_server"], "-m", gguf, "--host", "127.0.0.1", "--port", str(port), "-ngl", "99",
               "-c", str(ctx), "-b", "2048", "-ub", "512", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-np", "1",
               "--jinja", "--reasoning", "off", "--reasoning-budget", "0", "--cache-ram", "0", "--no-mmap"]
    log = open(HERE / f"llama-{port}.log", "w", encoding="utf-8")
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                if r.status == 200:
                    return process
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1.0)
    process.kill()
    raise RuntimeError("llama-server did not become healthy")


def to_record(parsed: dict) -> dict:
    decision = parsed.get("decision")
    ops = [op for op in parsed.get("operations") or [] if op in OPS]
    if decision == "action" and ops:
        return {"kind": "plan" if len(ops) > 1 else "action", "operation": ops[0], "effects": sorted(ops)}
    if decision == "action":
        return {"kind": "conversation", "conversation_kind": "knowledge", "note": "action_without_ops"}
    if decision == "clarify":
        return {"kind": "clarify"}
    if decision == "limit":
        return {"kind": "conversation", "conversation_kind": "unsupported"}
    return {"kind": "conversation", "conversation_kind": "knowledge"}


def main() -> None:
    import measure_mind_budget as budget

    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--gguf", default=MANIFEST["gguf"])
    parser.add_argument("--variant", default="min", choices=sorted(FORMAT_NOTE))
    parser.add_argument("--ctx", type=int, default=12288)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-tokens", type=int, default=160)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.set.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = rows[: args.limit or None]
    done = set()
    if args.out.is_file():
        done = {json.loads(line)["id"] for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()}
    system = POLICY + compact_catalog() + FORMAT_NOTE[args.variant]
    port = free_port()
    machine = budget.GpuSampler()
    machine.start()
    server = start_server(args.gguf, args.ctx, port)
    tree = budget.ProcessTreeGpuSampler(server.pid)
    ram = budget.RamSampler(server.pid)
    tree.start()
    ram.start()
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    fmt = {"type": "json_schema", "json_schema": {"name": "baxy_free_decision", "strict": True,
                                                  "schema": schema(args.variant)}}
    prompt_tokens = []
    try:
        post(url, {"messages": [{"role": "system", "content": system}, {"role": "user", "content": "Hola"}],
                   "response_format": fmt, "temperature": 0.0, "max_tokens": args.max_tokens, "cache_prompt": True})
        for row in rows:
            if row["id"] in done:
                continue
            messages = [{"role": "system", "content": system}]
            for turn in row.get("history") or []:
                messages.append({"role": turn["role"], "content": str(turn["content"])[:1500]})
            messages.append({"role": "user", "content": row["text"]})
            record = {"id": row["id"]}
            started = time.perf_counter()
            try:
                body = post(url, {"messages": messages, "response_format": fmt, "temperature": 0.0, "seed": 0,
                                  "max_tokens": args.max_tokens, "cache_prompt": True,
                                  "chat_template_kwargs": {"enable_thinking": False}})
                content = body["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                record.update(to_record(parsed))
                record["raw"] = parsed
                usage = body.get("usage") or {}
                prompt_tokens.append(usage.get("prompt_tokens") or 0)
                record["timings"] = {k: body.get("timings", {}).get(k) for k in ("prompt_n", "prompt_ms", "predicted_n",
                                                                                   "predicted_ms")}
            except Exception as error:  # noqa: BLE001 - a failed call is a measured failure
                record["error"] = f"{type(error).__name__}: {error}"[:300]
            record["latency_s"] = round(time.perf_counter() - started, 3)
            with args.out.open("a", encoding="utf-8", newline="\n") as sink:
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(row["id"], record.get("kind"), record.get("effects") or record.get("conversation_kind"),
                  record["latency_s"], flush=True)
    finally:
        server.kill()
        server.wait(timeout=30)
        for sampler in (tree, ram, machine):
            sampler.stop()
    meta = {"gguf": args.gguf, "variant": args.variant, "ctx": args.ctx, "system_chars": len(system),
            "peak_vram_server_mib": tree.peak_mib, "vram_telemetry": tree.telemetry_available,
            "peak_nvidia_smi_mib": machine.peak_mib, "peak_ram_server_mib": ram.peak_mib,
            "prompt_tokens_max": max(prompt_tokens or [0])}
    pathlib.Path(str(args.out) + ".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
