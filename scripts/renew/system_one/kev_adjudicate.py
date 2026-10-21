"""System One, phase 0 (B): a System One model (Kev, Laya, ...) on CPU as a second opinion on Qwen's own candidates.

usage: py -3.12 -X utf8 scripts/renew/system_one/kev_adjudicate.py <label> --signals s1-<qwen label> --gguf PATH
       [--server PATH] [--threads 8]
For each case of a qwen_signals.py run: one /v1/systemone request with two questions, both over options the case
itself offers: `operacion` (Qwen's chosen tool, its rivals, asking the person, answering in words) and `tipo` (act /
ask / answer in words / out of what BAXY does). Writes <banks>/runs/s1kev-<label>.jsonl and prints, against the bank's
expectation: Kev's accuracy, Qwen's, how often Kev is right where Qwen is wrong and the reverse, and what «act when they
agree, ask when they don't» would do. Nothing in the product changes.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bench_decision as bench  # noqa: E402

ANSWER = "responder_con_palabras"
KINDS = {"actuar": "hacer algo en el PC con una herramienta",
         "preguntar": "preguntar a la persona porque falta un dato o el pedido es ambiguo",
         "responder": "contestar con palabras, sin herramientas (charla, conocimiento, texto que no pide nada)",
         "no_se_puede": "decir que eso no lo hace: no hay una herramienta para ese pedido"}


STATE_CHARS = 1200


def state_text(text, history):
    """The state as plain text: kev.train serializes a dict as JSON while llama-server renders it with its own template,
    so training and serving read the same words only when it is already text."""
    previous = " | ".join(f'{m["role"]}: {m["content"]}' for m in (history or [])[-4:]) or "ninguna"
    # An encoder reads at most ~1k tokens (laya-multilingual's default): a pasted text keeps its start, as does history.
    text, previous = str(text)[:STATE_CHARS], previous[-STATE_CHARS // 2:]
    return (f"Pedido de la persona: {text}\nConversación previa: {previous}\n"
            "Lugar: asistente de escritorio BAXY en el PC Windows de la persona")


def post(port, body):
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/systemone", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as reply:
        return json.loads(reply.read())


def short(text, limit=220):
    text = " ".join(str(text).split())
    cut = text.find(". ")
    text = text[:cut + 1] if 0 < cut < limit else text
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def wanted(expect):
    """The option names that meet the bank's expectation, and the expected kind."""
    if expect["kind"] == "call":
        op, _, _ = bench.current(expect["op"])
        return ({op.replace(".", "_")} if op else set()), "actuar"
    if expect["kind"] == "call_any":
        ops = {bench.current(o)[0] for o in expect["ops"]}
        return {o.replace(".", "_") for o in ops if o}, "actuar"
    if expect["kind"] == "ask":
        return {"ask_user"}, "preguntar"
    return {ANSWER}, "responder"


def qwen_choice(row):
    if row["kind"] == "clarify":
        return "ask_user"
    if row["kind"] == "action":
        return str(row["operation"]).replace(".", "_")
    return ANSWER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--signals", required=True)
    parser.add_argument("--gguf", required=True)
    parser.add_argument("--server", default=r"F:\BAXYeval\llama\llama-server.exe")
    parser.add_argument("--threads", default="8")
    parser.add_argument("--port", type=int, default=18951, help="one per run that shares the machine")
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    args = parser.parse_args()
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.mind import Mind  # noqa: E402

    runs = bench.BANKS / "runs"
    mind = Mind(None, runs / f"s1kev-{args.label}.trace.jsonl")
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    described = {t["function"]["name"]: short(t["function"]["description"]) for t in mind.tools}
    described[ANSWER] = "contestar con palabras, sin usar herramientas"
    described["ask_user"] = "preguntar a la persona lo que falta o lo que no está claro"

    port = args.port
    log = open(runs / f"s1kev-{args.label}.server.log", "w", encoding="utf-8")
    server = subprocess.Popen([args.server, "-m", args.gguf, "--port", str(port), "-ngl", "0", "-t", args.threads,
                               "-c", "4096", "-np", "1", "-b", "2048", "-ub", "2048"],
                              stdout=log, stderr=subprocess.STDOUT)  # an encoder's input goes in one batch
    rows = [json.loads(line) for line in open(runs / f"s1-{args.signals}.jsonl", encoding="utf-8")]
    out_rows = []
    try:
        for _ in range(240):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                break
            except Exception:  # noqa: BLE001 - still loading
                time.sleep(0.5)
        for row in rows:
            if row["excluded"] or not row["signals"]:
                continue
            chosen = qwen_choice(row)
            options = [chosen] + [r["wire"] for r in row["rivals"] if r["known"]] + ["ask_user", ANSWER]
            options = list(dict.fromkeys(o for o in options if o in described))
            body = {"state": state_text(row["text"], row["history"]), "questions": {
                "operacion": {"type": "choice", "instructions": "¿Qué debe hacer el asistente con este pedido?",
                              "criteria": {o: described[o] for o in options}},
                "tipo": {"type": "choice", "instructions": "¿Qué tipo de respuesta pide este mensaje?",
                         "criteria": KINDS}}}
            started = time.monotonic()
            try:
                reply = post(port, body)
            except urllib.error.HTTPError as error:
                print(f'{row["id"]} server error {error.code}', flush=True)
                continue
            latency = time.monotonic() - started
            answers = reply.get("answers") or {}
            want_ops, want_kind = wanted(row["expect"])
            op = answers.get("operacion") or {}
            kind = answers.get("tipo") or {}
            out_rows.append({"id": row["id"], "family": row["family"], "qwen_ok": row["ok"], "qwen": chosen,
                             "options": options, "reachable": bool(want_ops & set(options)),
                             "kev": op.get("choice"), "kev_p": (op.get("probabilities") or {}).get(op.get("choice")),
                             "kev_conf": op.get("confidence"), "kev_ok": op.get("choice") in want_ops,
                             "kind": kind.get("choice"), "kind_ok": kind.get("choice") == want_kind,
                             "want_kind": want_kind, "latency_s": round(latency, 3),
                             "input_tokens": (reply.get("usage") or {}).get("input_tokens")})
            print(f'{row["id"]} qwen={"ok " if row["ok"] else "BAD"} {chosen:<28} kev={op.get("choice")} '
                  f'({(op.get("probabilities") or {}).get(op.get("choice"), 0):.2f}) tipo={kind.get("choice")} {latency*1000:.0f} ms',
                  flush=True)
        rss = round(psutil.Process(server.pid).memory_info().rss / 2**20)
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
    with open(runs / f"s1kev-{args.label}.jsonl", "w", encoding="utf-8", newline="\n") as out:
        for r in out_rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(out_rows)
    reach = [r for r in out_rows if r["reachable"]]
    q_bad = [r for r in reach if not r["qwen_ok"]]
    q_ok = [r for r in reach if r["qwen_ok"]]
    # The second opinion as a rule: act on Qwen's choice when Kev agrees; when not, ask the person.
    fixed = sum(1 for r in q_bad if r["kev"] != r["qwen"] and r["want_kind"] == "preguntar")
    stopped = sum(1 for r in q_bad if r["kev"] != r["qwen"])
    friction = sum(1 for r in q_ok if r["kev"] != r["qwen"])
    lat = [r["latency_s"] for r in out_rows]
    print(json.dumps({
        "cases": n, "reachable": len(reach),
        "qwen_ok": sum(r["qwen_ok"] for r in reach), "kev_ok": sum(r["kev_ok"] for r in reach),
        "kev_right_where_qwen_wrong": sum(r["kev_ok"] for r in q_bad), "qwen_wrong": len(q_bad),
        "kev_wrong_where_qwen_right": sum(not r["kev_ok"] for r in q_ok), "qwen_right": len(q_ok),
        "disagree_rule": {"qwen_wrong_stopped": stopped, "of_which_asking_was_right": fixed,
                          "qwen_right_questioned": friction},
        "kind_ok": sum(r["kind_ok"] for r in out_rows),
        "latency_p50_ms": round(statistics.median(lat) * 1000), "latency_p90_ms": round(statistics.quantiles(lat, n=10)[8] * 1000),
        "server_rss_mib": rss, "gguf": Path(args.gguf).name, "threads": args.threads}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
