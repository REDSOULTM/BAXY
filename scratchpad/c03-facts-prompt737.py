"""Isolate the BAXY writer prompt on frozen observations, retaining native K2 high."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "FACTS_PROMPT737"
LOCAL = Path(os.environ["LOCALAPPDATA"])
PRIVATE = LOCAL / "BAXY/C03-facts-prompt737-private"
SOURCE = LOCAL / "BAXY/C03-native-product736-qwen-private"
MANIFEST = LOCAL / "BAXYRuntime/mind-runtime-v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False)+"\n")


def prepare():
    assert not OUT.exists() and not PRIVATE.exists()
    assert read(BASE / "NATIVE_PRODUCT736/qwen/EXIT.json")["exit_code"] == 0
    assert sha(SOURCE / "review.json") == read(BASE / "NATIVE_PRODUCT736/qwen/ADJUDICATION.json")["review_sha256"]
    traces = [json.loads(line) for line in (SOURCE / "adapter-http.jsonl").open(encoding="utf-8-sig")]
    requests = {row["id"]: row for row in traces if row["stage"] == "request"}
    responses = [row for row in traces if row["stage"] == "response"]
    source_ast = ast.parse((ROOT / "src/baxy_mind/llm.py").read_text(encoding="utf-8"))
    system = next(ast.literal_eval(node.value) for node in source_ast.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "USER_MESSAGE_PROMPT" for target in node.targets))
    cases = []
    for row in read(SOURCE / "review.json"):
        facts = [draft for draft in row["compose"] if draft.get("stage") == "first"
                 and ("operation" in draft.get("payload", {}) or "completedStepsInOrder" in draft.get("payload", {}))]
        if not row["core_calls"] or not facts:
            continue
        first = facts[0]
        matches = []
        for response in responses:
            choices = response["response"].get("choices", [])
            if not choices or (choices[0].get("message", {}).get("content") or "").strip() != first["draft"]:
                continue
            wire = requests[response["id"]]["wire"]
            if len(wire["messages"]) != 2 or wire["messages"][0] != {"role": "system", "content": system}:
                continue
            user = wire["messages"][1]
            if user["role"] != "user" or "\nsituation: " not in user["content"]:
                continue
            question, tail = user["content"].split("\nsituation: ", 1)
            parsed, _ = json.JSONDecoder().raw_decode(tail)
            if question == row["text"] and parsed == first["payload"]:
                matches.append(wire)
        assert matches and all(item == matches[0] for item in matches), row["case_id"]
        cases.append({"case_id": row["case_id"], "source_turn": row["turn_id"], "group": row["group"],
            "text": row["text"], "criterion": row["criterion"], "language": first["language"],
            "facts": first["payload"], "product_messages": matches[0]["messages"],
            "native_messages": [{"role": "user", "content": row["text"]+"\n\n"+json.dumps(first["payload"], ensure_ascii=False)}]})
    assert len(cases) == 57, len(cases)
    reference = read(BASE / "K2_HORIZON_NATIVE699/run-37-q4-high-practical699/PREREG.json")
    command = list(reference["command"])
    binary, model = Path(command[0]), Path(command[command.index("-m")+1])
    assert sha(model) == reference["model_sha256"] and sha(MANIFEST) == reference["manifest_sha256"]
    for name, expected in reference["backend_files"].items():
        assert sha(binary.parent / name) == expected
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command[command.index("--port")+1] = str(port)
    OUT.mkdir()
    PRIVATE.mkdir()
    write(PRIVATE / "cases.json", cases)
    plan = {"utc": datetime.now(timezone.utc).isoformat(), "command": command,
        "model_sha256": reference["model_sha256"], "backend_files": reference["backend_files"],
        "manifest_sha256": reference["manifest_sha256"], "source_review_sha256": sha(SOURCE / "review.json"),
        "cases_sha256": sha(PRIVATE / "cases.json"), "driver_sha256": sha(Path(__file__)),
        "llm_source_sha256": sha(ROOT / "src/baxy_mind/llm.py"),
        "case_ids": [row["case_id"] for row in cases], "cases": len(cases), "calls": len(cases)*2,
        "arms": ["native_high", "baxy_prompt_high"],
        "method": "All57 product736 cases with a captured fresh typed observation and first writer draft, regardless of pass/fail. Same frozen question/facts, weights/backend/sampler/high/32768output/8192context in both arms. Alternate arm order per case. Only message prompt component changes: user question plus JSON facts versus exact captured BAXY writer messages. No policy, validator, kernel or provider executes here. This isolates the complete writer prompt, not individual clauses. All requests use native embedded template, T1/p.95/k0, seed0, cache_prompt false and streaming.",
        "scoring": "Judge final content against supplied facts and requested subject/units/language; distinguish insufficient provider facts from invented certainty. Keep complete quality and completion within4s separate. The120s offline observation ceiling does not extend any product deadline, and is not a successful response if reached. Do not claim end-to-end success or survey coverage. Streaming latency is diagnostic and needs later nonstreaming product confirmation.",
        "official_source": "https://huggingface.co/IFM/K2-Horizon-3.7B#best-practices",
        "recipe": "IFM recommends high/T1/p.95 and at least32768 output tokens. Both arms use32768; 8192 context, Q4 and local llama backend remain practical deviations from official BF16/SGLang evaluation. Any context exhaustion/shift or length cutoff must remain visible, never count as a shorter success. Medium/low are not used in this comparison.",
        "limits": {"request_seconds": 120, "product_reference_seconds": 4, "minimum_free_ram_mib": 768, "gpu_stop_mib": 3800},
        "adopted": False, "model_promoted": False, "survey_coverage_added": 0}
    write(OUT / "PREREG.json", plan)
    return plan, cases


def main():
    assert not any((p.info["name"] or "").lower() in {"llama-server.exe", "baxy.exe", "baxy-core.exe", "testhost.exe"}
                   for p in psutil.process_iter(["name"]))
    assert psutil.virtual_memory().available >= 2048*2**20
    plan, cases = prepare()
    command = plan["command"]
    endpoint = f"http://127.0.0.1:{command[command.index('--port')+1]}"
    env = os.environ.copy()
    env["PATH"] = "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;"+env["PATH"]
    process = gpu = ram = watcher = None
    stop, violations = threading.Event(), []
    started, completed = time.monotonic(), 0

    def guard():
        while not stop.wait(.25):
            if (gpu.peak_mib or 0) >= 3800:
                violations.append("owned_gpu_bound")
            if psutil.virtual_memory().available < 768*2**20:
                violations.append("free_ram_bound")
            if violations:
                if process.poll() is None:
                    process.terminate()
                return

    def post_json(path, payload):
        request = urllib.request.Request(endpoint+path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        with (PRIVATE / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=Path(command[0]).parent, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        write(OUT / "PROCESS.json", {"driver_pid": os.getpid(), "server_pid": process.pid, "command": command})
        gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
        gpu.start()
        ram.start()
        watcher = threading.Thread(target=guard, daemon=True)
        watcher.start()
        while time.monotonic()-started < 120:
            assert process.poll() is None
            try:
                with urllib.request.urlopen(endpoint+"/health", timeout=2) as response:
                    if json.load(response).get("status") == "ok":
                        break
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(.25)
        else:
            raise TimeoutError("server startup")
        with urllib.request.urlopen(endpoint+"/props", timeout=10) as response:
            write(PRIVATE / "props.json", json.load(response))
        planned = []
        for index, case in enumerate(cases):
            order = ["native_high", "baxy_prompt_high"]
            if index % 2:
                order.reverse()
            for arm in order:
                payload = {"messages": copy.deepcopy(case["native_messages" if arm == "native_high" else "product_messages"]),
                    "temperature": 1.0, "top_p": .95, "top_k": 0, "min_p": 0.0, "repeat_penalty": 1.0,
                    "presence_penalty": 0.0, "max_tokens": 32768, "seed": 0, "cache_prompt": False,
                    "chat_template_kwargs": {"reasoning_effort": "high"}, "stream": True,
                    "stream_options": {"include_usage": True}}
                rendered = post_json("/apply-template", payload)["prompt"]
                assert rendered.rstrip().endswith("<ifm|think>"), "Native high prefix was changed"
                tokens = post_json("/tokenize", {"content": rendered, "add_special": False})["tokens"]
                assert len(tokens) < 7168, "Prompt leaves insufficient space in practical context"
                append(PRIVATE / "rendered-prompts.jsonl", {"case_id": case["case_id"], "arm": arm, "prompt": rendered, "tokens": len(tokens)})
                planned.append({"case_id": case["case_id"], "arm": arm, "prompt_tokens": len(tokens), "payload": payload})
        write(PRIVATE / "planned-requests.json", planned)
        write(OUT / "PREFLIGHT.json", {"pairs": len(cases), "requests": len(planned), "all_high_prefixes": True,
            "max_prompt_tokens": max(row["prompt_tokens"] for row in planned), "planned_requests_sha256": sha(PRIVATE / "planned-requests.json")})
        print(json.dumps({"stage": "preflight_complete", "cases": len(cases), "calls": len(planned)}), flush=True)
        with (PRIVATE / "stream.jsonl").open("w", encoding="utf-8") as trace:
            for row in planned:
                assert sha(Path(__file__)) == plan["driver_sha256"] and not violations
                before = time.monotonic()
                record = {key: row[key] for key in ["case_id", "arm", "prompt_tokens"]}
                record.update(content="", reasoning_content="")
                request = urllib.request.Request(endpoint+"/v1/chat/completions", data=json.dumps(row["payload"]).encode(), headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(request, timeout=120) as response:
                        for line in response:
                            elapsed = time.monotonic()-before
                            if elapsed > 120:
                                record["error"] = "offline_observation_deadline120s"
                                break
                            if not line.startswith(b"data: "):
                                continue
                            data = line[6:].strip()
                            if data == b"[DONE]":
                                break
                            event = json.loads(data)
                            trace.write(json.dumps({"case_id": row["case_id"], "arm": row["arm"], "seconds": elapsed, "event": event}, ensure_ascii=False)+"\n")
                            for key in ["usage", "timings", "error"]:
                                if event.get(key):
                                    record[key] = event[key]
                            for choice in event.get("choices", []):
                                delta = choice.get("delta", {})
                                if delta.get("content"):
                                    record.setdefault("first_content_seconds", elapsed)
                                for key in ["content", "reasoning_content"]:
                                    record[key] += delta.get(key) or ""
                                if choice.get("finish_reason"):
                                    record["finish_reason"] = choice["finish_reason"]
                except Exception as error:
                    record["error"] = str(error)
                    if isinstance(error, urllib.error.HTTPError):
                        record["body"] = error.read().decode(errors="replace")
                record["seconds"] = time.monotonic()-before
                record["complete_within_product_reference_4s"] = bool(record["content"].strip() and record.get("finish_reason") == "stop" and not record.get("error") and record["seconds"] <= 4)
                record["context_shift_possible"] = row["prompt_tokens"]+record.get("usage", {}).get("completion_tokens", 0) >= 8192
                append(PRIVATE / "results.jsonl", record)
                trace.flush()
                completed += 1
                print(json.dumps({"case_id": row["case_id"], "arm": row["arm"], "seconds": record["seconds"],
                    "finish_reason": record.get("finish_reason"), "error": record.get("error"), "completed": completed}), flush=True)
    finally:
        stop.set()
        if process is not None:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=20)
        if watcher is not None:
            watcher.join(timeout=3)
        if gpu is not None:
            gpu.stop()
            ram.stop()
        write(OUT / "RESULT.json", {"calls_completed": completed, "calls_planned": len(cases)*2,
            "gpu_peak_mib": gpu.peak_mib if gpu else None, "ram_peak_mib": ram.peak_mib if ram else None,
            "seconds": time.monotonic()-started, "violations": violations,
            "manifest_unchanged": sha(MANIFEST) == plan["manifest_sha256"],
            "source_unchanged": sha(ROOT / "src/baxy_mind/llm.py") == plan["llm_source_sha256"],
            "driver_unchanged": sha(Path(__file__)) == plan["driver_sha256"],
            "scope": "Server-only native prompt diagnostic; offline streaming. Not product deadline acceptance, UI/voice, model promotion or coverage.",
            "adopted": False, "model_promoted": False, "survey_coverage_added": 0})


if __name__ == "__main__":
    main()
