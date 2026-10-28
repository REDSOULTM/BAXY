"""The App's guards for the decision benches (C62): what the person sees, beside the model's first decision.

bench_decision and bench_sesion_larga judge the mind's first decision of a turn. In the App that call goes first through
its shape guards (NativeTurnLoop: NetworkEgress.Unsaid, SaidFolders, SaidApplication, SaidVerbs), which refuse it and
send it back to the model with what to do next, or route it into the folder or the app the person named: V6D278's
filesystem_list and FER022's message.draft were wrong first decisions the App never runs. With --guardas the benches
also judge the decision the person sees: each call through the App's own guards (the oracle, tests/Baxy.GuardOracle,
never a copy of them here), a refused one back to the model with the App's refusal, until a call goes (as it would run)
or the model answers in words. The first decision stays the bench's number, as before; the one seen is the second.

Oracle protocol, one JSON object per line each way: {"heard": words, "answering": bool} → {}; {"asked": true} → {};
{"call": op, "arguments": {...}} → {"refused": observation} or {"operation": op, "arguments": {...}, "note": ...};
{"ran": op, "arguments": {...}, "observation": text} → {}; {"reset": true} → {}.
"""
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

import run_meta


class Guards:
    """The oracle's process for one run: the executable `oracle`, closed by close()."""

    def __init__(self, oracle: str) -> None:
        self._process = subprocess.Popen([oracle], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)

    def _ask(self, request: dict) -> dict:
        assert self._process.stdin is not None and self._process.stdout is not None
        self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            # A run that went on without its guards would label first decisions as the ones seen.
            raise RuntimeError(f"the guard oracle exited ({self._process.poll()})")
        return json.loads(line)

    def reset(self) -> None:
        self._ask({"reset": True})

    def heard(self, words: str, answering: bool = False) -> None:
        self._ask({"heard": words, "answering": answering})

    def asked(self) -> None:
        self._ask({"asked": True})

    def call(self, operation: str, arguments: dict | None) -> dict:
        return self._ask({"call": operation, "arguments": arguments or {}})

    def ran(self, operation: str, arguments: dict | None, observation: str) -> None:
        self._ask({"ran": operation, "arguments": arguments or {}, "observation": observation})

    def close(self) -> None:
        if self._process.poll() is None:
            assert self._process.stdin is not None
            self._process.stdin.close()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()  # its own child, by its handle


def refusal_code(observation: str) -> str:
    """The code of a refusal the oracle gave (its «error», else its «status»)."""
    try:
        facts = json.loads(observation)
    except (TypeError, ValueError):
        return "?"
    return str(facts.get("error") or facts.get("code") or facts.get("status") or "?") if isinstance(facts, dict) else "?"


def seen(mind: Any, request_id: Any, first: dict, guards: Guards, limit: int,
         observe: Callable[[str, dict | None, int], str] | None = None) -> tuple[dict, list[str], list[str], dict]:
    """The turn from its first decision as the App runs it, up to `limit` calls: each call through the guards, a refused
    one back to the model with its refusal. Returns the decision the person sees (the first call that goes, as it would
    run, or the model's words), the calls that went, the refusals' codes and the turn's last result. With `observe` (op, arguments, index → the
    call's result) the turn goes on after a call goes, as the session bench closes it; without it, it stops there."""
    result, decision, went, refused, calls = first, None, [], [], 0
    while result.get("kind") == "action" and calls < limit:
        calls += 1
        op = str(result.get("operation"))
        ruling = guards.call(op, result.get("arguments"))
        if "refused" in ruling:
            refused.append(refusal_code(ruling["refused"]))
            observation = ruling["refused"]
        else:
            ran = {"kind": "action", "operation": ruling.get("operation") or op,
                   "arguments": ruling.get("arguments", result.get("arguments"))}
            decision = decision or ran
            went.append(ran["operation"])
            if observe is None:
                return decision, went, refused, result
            observation = observe(ran["operation"], ran["arguments"], calls)
            guards.ran(ran["operation"], ran["arguments"], observation)
        result = mind.continue_turn(request_id, observation, final=calls == limit)
    if result.get("kind") == "clarify":  # the App's «question» step (NetworkEgress.Asked)
        guards.asked()
    return decision or result, went, refused, result


def seen_summary(counted: list[dict], oracle: str | None) -> dict:
    """The run's second number, beside its «ok»: the decisions the person sees, and the oracle that judged them."""
    if not oracle:
        return {}
    ok = sum(bool(r.get("ok_seen")) for r in counted)
    return {"ok_seen": ok, "accuracy_seen": round(ok / max(1, len(counted)), 4),
            "guardas": {"path": oracle, "sha256": run_meta.sha256_file(Path(oracle))},
            "refused": sum(bool(r.get("refused")) for r in counted)}
