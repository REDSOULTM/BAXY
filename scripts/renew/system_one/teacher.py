"""System One, Laya v2: a larger local model (Qwen3.6-35B-A3B, the judge of the falsehood bench) as the teacher.

usage: py -3.12 -X utf8 scripts/renew/system_one/teacher.py IN.jsonl OUT.jsonl [--gguf PATH] [--parallel 4]
       py -3.12 -X utf8 scripts/renew/system_one/teacher.py --paraphrase IDS.jsonl OUT.jsonl
Label mode: each record of a Laya/Kev file (state + typed choice questions) is asked as a lettered exam (Lev's label
reading, ADR-027: the evidence, the criterion, the options as A. B. C.; one token; the letters' probabilities), and OUT
gets one line per record: {"teacher": {question: {option: p}}}. Paraphrase mode: for each case of an ids file, three new
wordings of the same request (Chilean colloquial, spanglish, dictated without punctuation and with a misheard word), as
{"id", "variants": [...]}. One llama-server with the whole model on the GPU (it fits the 16 GB of the training PC).
"""
import argparse
import concurrent.futures
import json
import math
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = [18961]
SYSTEM = ("Eres un modelo de decisión. Lees la evidencia y respondes el criterio eligiendo exactamente una de las "
          "opciones de la lista. Nunca explicas. Respondes sólo con la letra de la opción.")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PARAPHRASE = ("Esta es una frase que una persona le dijo a BAXY, su asistente de escritorio en Windows:\n«{text}»\n\n"
              "Escribe otras tres formas de decir EXACTAMENTE lo mismo (mismo pedido, mismos nombres, mismos números, "
              "nada que no esté): 1) como la diría un chileno de forma coloquial; 2) en spanglish, mezclando inglés y "
              "español; 3) como la entendería un dictado por voz: sin mayúsculas ni puntuación y con una palabra mal "
              "reconocida que suene parecida. Si la frase no pide nada, las variantes tampoco piden nada.")
PARAPHRASE_SCHEMA = {"type": "object", "properties": {"variantes": {"type": "array", "items": {"type": "string"},
                                                                     "minItems": 3, "maxItems": 3}},
                     "required": ["variantes"]}


def post(path, body, timeout=300):
    request = urllib.request.Request(f"http://127.0.0.1:{PORT[0]}{path}", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read())


def exam(state, question):
    keys = list(question["criteria"])
    lines = [f"{LETTERS[i]}. {key}" + (f": {question['criteria'][key]}" if question["criteria"][key] else "")
             for i, key in enumerate(keys)]
    user = (f"# Evidencia\n{state}\n\n# Criterio\n{question['instructions']}\n\n# Opciones\n" + "\n".join(lines)
            + "\n\nResponde sólo con la letra de la mejor opción.")
    reply = post("/v1/chat/completions", {
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "max_tokens": 1, "temperature": 0.0, "logprobs": True, "top_logprobs": 20,
        "chat_template_kwargs": {"enable_thinking": False}})
    top = ((reply["choices"][0].get("logprobs") or {}).get("content") or [{}])[0].get("top_logprobs") or []
    letters = {}
    for item in top:
        letter = item["token"].strip()
        if len(letter) == 1 and letter in LETTERS[:len(keys)]:
            letters[letter] = letters.get(letter, 0.0) + math.exp(item["logprob"])
    mass = sum(letters.values())
    if mass < 0.5:  # the teacher did not answer with a letter: no soft label for this question
        return None
    return {keys[LETTERS.index(k)]: round(v / mass, 5) for k, v in letters.items()}


def label(record):
    return {"teacher": {q: exam(record["state"], body) for q, body in record["questions"].items()}}


def paraphrase(case):
    reply = post("/v1/chat/completions", {
        "messages": [{"role": "user", "content": PARAPHRASE.format(text=case["text"][:600])}],
        "max_tokens": 400, "temperature": 0.7, "seed": 0, "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {"name": "variantes", "schema": PARAPHRASE_SCHEMA}}})
    try:
        variants = json.loads(reply["choices"][0]["message"]["content"])["variantes"]
    except (KeyError, ValueError, TypeError):
        variants = []
    return {"id": case["id"], "variants": [str(v).strip() for v in variants if str(v).strip()][:3]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inp")
    parser.add_argument("out")
    parser.add_argument("--paraphrase", action="store_true")
    parser.add_argument("--gguf", default=r"F:\BAXYeval\models\Qwen3.6-35B-A3B-MTP-UD-IQ3_XXS.gguf")
    parser.add_argument("--server", default=r"F:\BAXYeval\llama\llama-server.exe")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--port", type=int, default=18961)
    args = parser.parse_args()
    PORT[0] = args.port
    items = [json.loads(line) for line in open(args.inp, encoding="utf-8")]
    log = open(Path(args.out).with_suffix(".server.log"), "w", encoding="utf-8")
    server = subprocess.Popen([args.server, "-m", args.gguf, "--host", "127.0.0.1", "--port", str(PORT[0]), "-ngl", "99",
                               "-c", str(4096 * args.parallel), "-np", str(args.parallel), "-fa", "on", "--jinja"],
                              stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(600):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT[0]}/health", timeout=2)
                break
            except Exception:  # noqa: BLE001 - still loading
                time.sleep(1)
        work = paraphrase if args.paraphrase else label
        started = time.monotonic()
        with open(args.out, "w", encoding="utf-8", newline="\n") as out, \
                concurrent.futures.ThreadPoolExecutor(args.parallel) as pool:
            for n, result in enumerate(pool.map(work, items), 1):  # map keeps the input order
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                if n % 100 == 0:
                    out.flush()
                    print(f"{n}/{len(items)} {time.monotonic() - started:.0f}s", flush=True)
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
    print("done", args.out)


if __name__ == "__main__":
    sys.exit(main())
