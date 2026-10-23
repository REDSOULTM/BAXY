"""What the request after a call reads again, with the call's booleans as the template writes them and as the model
wrote them (aid «calls_as_written», w6-lat). Runs on a llama-server already up (a CPU one is enough: -ngl 0 -dev none
-c 8192), with a few tools of the product's catalog so the prompt fits.

usage: py -3.12 -X utf8 scripts/renew/medir_relectura.py --url http://127.0.0.1:18555 --catalog FILE
Per request: the decision (the chat with its call grammar), then the same request after it with the call and a result,
once as the template writes it and once as the model wrote it; prints prompt_n and cache_n of each. Writes nothing.
Measured 2026-10-23 (b11609, BAXY-Qwen3.5-4B-ft-c2e1 Q4_K_M, CPU): «silencia el audio» 54 → 23 tokens, «abre la
calculadora en primer plano» 65 → 23. The server's log (-lv 4) tells why: «checking sim = 0.980 (1706/1740)» and
«restored context checkpoint … n_tokens = 1686»: the slot went back to its checkpoint 4 tokens before the decision's end.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ("audio.mute", "app.open", "input.visible.controls", "file.write")
REQUESTS = ("silencia el audio", "abre la calculadora en primer plano",
            "mira los controles de la ventana de Spotify incluyendo el texto")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18555")
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from baxy_mind.mind import SYSTEM, _as_written, _model_schema  # noqa: E402

    def post(path: str, body: dict) -> dict:
        request = urllib.request.Request(args.url + path, data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=600) as reply:
            return json.loads(reply.read())

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    tools = [{"type": "function", "function": {
        "name": cap["name"].replace(".", "_"), "description": str(cap.get("description") or "")[:300],
        "parameters": {**_model_schema(cap.get("argumentsSchema") or {}), "type": "object"}}}
        for cap in catalog.get("capabilities") or [] if cap.get("name") in TOOLS]
    for text in REQUESTS:
        base = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
        body = {"messages": base, "tools": tools, "chat_template_kwargs": {"enable_thinking": False},
                "temperature": 0.0, "max_tokens": 80, "cache_prompt": True, "id_slot": 0}
        for arm in ("template", "as_written"):
            decided = post("/v1/chat/completions", body)
            calls = decided["choices"][0]["message"].get("tool_calls") or []
            if not calls:
                print(f"{text!r}: no call")
                break
            call = calls[0]["function"]
            history = [*base, {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": call["name"], "arguments": json.dumps(json.loads(call["arguments"]), ensure_ascii=False)}}]},
                {"role": "tool", "tool_call_id": "c1", "content": '{"status":"completed"}'}]
            if arm == "as_written":
                history = _as_written(history)
            after = post("/v1/chat/completions", {**body, "messages": history, "max_tokens": 1})["timings"]
            print(f"{text!r} {call['arguments']} {arm:<10} prompt_n {after['prompt_n']:4d} "
                  f"cache_n {after.get('cache_n')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
