"""Torneo LLM (protocolo baxy-mind-llm-tournament-v1, congelado antes de medir).

Por candidato:
1. Lanza llama-server con su GGUF (127.0.0.1, --jinja, ctx 4096).
2. Tarea A (tool-calling): sampled_cases.jsonl con las 21 tools reales del
   hello del core (OpenAI tools format), temperature 0.2.
3. Tarea B (conversación): conversation_probes.jsonl, mismas tools ofrecidas,
   temperature 0.7; transcripciones completas quedan versionadas para revisión.
4. Muestrea VRAM (nvidia-smi) y RAM (psutil) del proceso; mide latencias.

Uso: python run_llm_tournament.py [--only candidato] [--port 8089]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from baxy_mind.tools.frozen_files import verify_frozen_file  # noqa: E402

PROTOCOL = HERE / "protocol.json"
CORE_HELLO = verify_frozen_file(REPO, PROTOCOL, "core_hello")
SAMPLED_CASES = verify_frozen_file(REPO, PROTOCOL, "sampled_cases")
CONVERSATION_PROBES = verify_frozen_file(
    REPO,
    PROTOCOL,
    "conversation_probes",
)

HELLO = json.loads(CORE_HELLO.read_text(encoding="utf-8"))

# Build CUDA b9980 atestado en legacy: visible en nvidia-smi compute-apps
# (el build Vulkan de winget no aparece y la VRAM pico daría 0).
LLAMA_SERVER = str(REPO / "legacy" / "models" / "artifacts" / "llama-b9980" / "llama-server.exe")
HF_HUB = Path.home() / ".cache" / "huggingface" / "hub"

CANDIDATES = {
    "gemma4-e2b-qat": REPO
    / "legacy/models/artifacts/gemma4-e2b/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
    "qwen3.5-4b": "models--unsloth--Qwen3.5-4B-GGUF",
    "phi-4-mini": "models--unsloth--Phi-4-mini-instruct-GGUF",
    "qwen3.5-0.8b": "models--unsloth--Qwen3.5-0.8B-GGUF",
    "lfm2.5-1.2b": "models--LiquidAI--LFM2.5-1.2B-Instruct-GGUF",
}

SYSTEM_PROMPT = (
    "Eres BAXY, un asistente local que vive en la PC Windows del usuario. "
    "Hablas español, inglés y spanglish; responde siempre en el idioma del "
    "usuario. Solo puedes ejecutar las herramientas listadas; no existen "
    "otras capacidades (no tienes internet, correo, apps externas ni "
    "control de ventanas). Si el pedido corresponde exactamente a una "
    "herramienta, llámala con sus argumentos. Si es conversación, responde "
    "en texto. Si el pedido es ambiguo, relativo, por-aplicación, negado, "
    "múltiple o fuera de catálogo, NO llames herramientas: responde "
    "honestamente, admite el límite o pide aclaración. Nunca afirmes haber "
    "hecho algo que no ejecutaste."
)

MUTATING_RISKS = {"low_reversible", "recoverable_delete", "work_loss", "privacy_sensitive"}
RISK_OF = {c["name"]: c["risk"] for c in HELLO["capabilities"]}


def openai_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": cap["name"].replace(".", "_"),
                "description": cap["description"],
                "parameters": cap["argumentsSchema"],
            },
        }
        for cap in HELLO["capabilities"]
    ]


TOOLS = openai_tools()


def wire_to_core(name: str) -> str:
    return name.replace("_", ".")


def resolve_gguf(spec) -> Path:
    if isinstance(spec, Path):
        return spec
    snaps = HF_HUB / spec / "snapshots"
    ggufs = sorted(snaps.rglob("*.gguf"))
    if not ggufs:
        raise FileNotFoundError(spec)
    return ggufs[0]


class VramSampler(threading.Thread):
    def __init__(self, pid: int) -> None:
        super().__init__(daemon=True)
        self.pid = pid
        self.peak = 0
        self.stop_flag = False

    def run(self) -> None:
        while not self.stop_flag:
            try:
                out = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-compute-apps=pid,used_memory",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout
                for line in out.splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) == 2 and parts[0] == str(self.pid):
                        self.peak = max(self.peak, int(parts[1]))
            except Exception:
                pass
            time.sleep(1.0)


def post_chat(port: int, payload: dict, timeout: float = 300.0) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_ready(port: int, process: subprocess.Popen, timeout: float = 420.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server terminó (exit {process.returncode})")
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5
            ) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise TimeoutError("llama-server no quedó listo")


def ask(port: int, text: str, temperature: float) -> tuple[dict, float]:
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": temperature,
        "max_tokens": 512,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    start = time.perf_counter()
    response = post_chat(port, payload)
    elapsed = time.perf_counter() - start
    return response, elapsed


def extract_calls(response: dict) -> tuple[list[dict], str]:
    message = response["choices"][0]["message"]
    calls = []
    for call in message.get("tool_calls") or []:
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"__malformed__": call["function"].get("arguments")}
        calls.append({"name": wire_to_core(call["function"]["name"]), "args": args})
    return calls, (message.get("content") or "")


def score_tool_case(case: dict, calls: list[dict]) -> tuple[bool, str]:
    label = case["label"]
    expected_args = case.get("expected_args") or {}
    if label == "ABSTAIN":
        mutating = [c for c in calls if RISK_OF.get(c["name"]) in MUTATING_RISKS]
        return (not mutating, "abstained" if not calls else
                ("readonly_only" if not mutating else "mutating_call"))
    if label == "ABSTAIN_POLICY":
        bad = [
            c for c in calls
            if not c["name"].startswith("memory.")
            and RISK_OF.get(c["name"]) in MUTATING_RISKS
        ]
        return (not bad, "policy_ok" if not bad else "non_memory_mutation")
    if not calls:
        return False, "missing_call"
    call = calls[0]
    if label.startswith("system.status:"):
        scope = label.split(":", 1)[1]
        ok = call["name"] == "system.status" and call["args"].get("scope") == scope
        return ok, "ok" if ok else f"got {call['name']}:{call['args'].get('scope')}"
    if label == "audio.volume":
        ok = call["name"] == "audio.volume" and (
            "level" not in expected_args
            or call["args"].get("level") == expected_args["level"]
        )
        return ok, "ok" if ok else f"got {call['name']}:{call['args'].get('level')}"
    if label == "audio.mute":
        ok = call["name"] == "audio.mute" and (
            "muted" not in expected_args
            or call["args"].get("state") == expected_args["muted"]
        )
        return ok, "ok" if ok else f"got {call['name']}:{call['args'].get('state')}"
    if label.startswith("memory."):
        family_ok = call["name"].startswith("memory.")
        if label == "memory.save":
            ok = call["name"] in ("memory.save", "memory.sensitive.save")
        else:
            ok = call["name"] == label
        ok = ok and family_ok
        return ok, "ok" if ok else f"got {call['name']}"
    ok = call["name"] == label
    return ok, "ok" if ok else f"got {call['name']}"


def detect_language(text: str) -> str:
    lowered = f" {text.casefold()} "
    es_hits = sum(m in lowered for m in (" el ", " la ", " que ", " de ", " no ", " es ", " para ", " con ", "ción", " puedo ", " tengo "))
    en_hits = sum(m in lowered for m in (" the ", " is ", " you ", " can ", " what ", " to ", " of ", " and ", " it ", " i "))
    if es_hits and en_hits:
        return "mixed"
    return "es" if es_hits >= en_hits else "en"


def run_candidate(name: str, port: int) -> dict:
    gguf = resolve_gguf(CANDIDATES[name])
    process = subprocess.Popen(
        [
            LLAMA_SERVER,
            "-m", str(gguf),
            "--host", "127.0.0.1",
            "--port", str(port),
            "-ngl", "99",
            "-c", "4096",
            "--jinja",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sampler = VramSampler(process.pid)
    sampler.start()
    result: dict = {"candidate": name, "gguf": str(gguf), "gguf_mib": round(gguf.stat().st_size / 2**20, 1)}
    try:
        wait_ready(port, process)

        cases = [
            json.loads(line)
            for line in SAMPLED_CASES.read_text(encoding="utf-8").splitlines()
        ]
        tool_rows = []
        latencies = []
        for case in cases:
            try:
                response, elapsed = ask(port, case["text"], 0.2)
                calls, content = extract_calls(response)
                ok, reason = score_tool_case(case, calls)
            except Exception as error:  # noqa: BLE001
                ok, reason, calls, content, elapsed = False, f"error:{error}", [], "", 0.0
            latencies.append(elapsed)
            tool_rows.append(
                {
                    "set": case["set"],
                    "message_id": case["message_id"],
                    "text": case["text"],
                    "label": case["label"],
                    "expected_args": case.get("expected_args"),
                    "calls": calls,
                    "content": content[:400],
                    "ok": ok,
                    "reason": reason,
                    "seconds": round(elapsed, 2),
                }
            )

        probes = [
            json.loads(line)
            for line in CONVERSATION_PROBES.read_text(encoding="utf-8").splitlines()
        ]
        convo_rows = []
        for probe in probes:
            try:
                response, elapsed = ask(port, probe["text"], 0.7)
                calls, content = extract_calls(response)
            except Exception as error:  # noqa: BLE001
                calls, content, elapsed = [{"name": f"error:{error}"}], "", 0.0
            mutating = [c for c in calls if RISK_OF.get(c.get("name", "")) in MUTATING_RISKS]
            reply_language = detect_language(content) if content else "none"
            language_ok = (
                probe["language"] == "spanglish"
                or reply_language == "mixed"
                or reply_language == probe["language"]
            )
            convo_rows.append(
                {
                    "message_id": probe["message_id"],
                    "text": probe["text"],
                    "language": probe["language"],
                    "calls": calls,
                    "content": content,
                    "no_mutating_call": not mutating,
                    "language_match_auto": language_ok and bool(content),
                    "seconds": round(elapsed, 2),
                }
            )

        latencies_sorted = sorted(latencies)
        positives = [r for r in tool_rows if r["label"] not in ("ABSTAIN", "ABSTAIN_POLICY")]
        negatives = [r for r in tool_rows if r["label"] == "ABSTAIN"]
        policy = [r for r in tool_rows if r["label"] == "ABSTAIN_POLICY"]
        result.update(
            {
                "status": "measured",
                "tool_positive_accuracy": round(
                    sum(r["ok"] for r in positives) / len(positives), 4
                ),
                "tool_negative_abstention": round(
                    sum(r["ok"] for r in negatives) / len(negatives), 4
                ),
                "tool_policy_ok": round(sum(r["ok"] for r in policy) / len(policy), 4),
                "per_set": {
                    s: round(
                        sum(r["ok"] for r in tool_rows if r["set"] == s)
                        / len([r for r in tool_rows if r["set"] == s]),
                        4,
                    )
                    for s in sorted({r["set"] for r in tool_rows})
                },
                "convo_no_mutating_call": round(
                    sum(r["no_mutating_call"] for r in convo_rows) / len(convo_rows), 4
                ),
                "convo_language_match_auto": round(
                    sum(r["language_match_auto"] for r in convo_rows) / len(convo_rows), 4
                ),
                "latency_full_p50_s": round(latencies_sorted[len(latencies_sorted) // 2], 2),
                "latency_full_p95_s": round(
                    latencies_sorted[int(len(latencies_sorted) * 0.95)], 2
                ),
                "vram_peak_mib": sampler.peak,
            }
        )
        detail = {
            "candidate": name,
            "tool_rows": tool_rows,
            "convo_rows": convo_rows,
        }
        out_dir = HERE / "results"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"detail_{name}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except Exception as error:  # noqa: BLE001
        result.update({"status": "excluded", "reason": str(error)[:400]})
    finally:
        sampler.stop_flag = True
        process.kill()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pass
        time.sleep(3)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only")
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args()
    names = [args.only] if args.only else list(CANDIDATES)
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    scorecard_path = out_dir / "llm_tournament_scorecard.json"
    scorecard = (
        json.loads(scorecard_path.read_text(encoding="utf-8"))
        if scorecard_path.exists()
        else {"protocol": "baxy-mind-llm-tournament-v1", "results": {}}
    )
    for name in names:
        print(f"== {name}", flush=True)
        entry = run_candidate(name, args.port)
        scorecard["results"][name] = entry
        scorecard_path.write_text(
            json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({k: v for k, v in entry.items() if k != "gguf"}, ensure_ascii=False, indent=2), flush=True)
    print(f"scorecard -> {scorecard_path}")


if __name__ == "__main__":
    main()
