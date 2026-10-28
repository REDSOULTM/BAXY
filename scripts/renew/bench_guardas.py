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
{"ran": op, "arguments": {...}, "observation": text} → {}; {"reset": true} → {}. Any other answer stops the run
(GuardOracleError): a run that went on without its guards would report first decisions as the ones seen.
"""
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, NamedTuple

import run_meta

# The note the mind adds to the person's words starts so (the clock, a pending call, a cut): never their words (Mind._said).
NOTE = "["
ASK_USER = "ask_user"


class GuardOracleError(RuntimeError):
    """The oracle died or answered out of its protocol: the run stops."""


class Guards:
    """The oracle's process for one run: the executable `oracle`, closed by close()."""

    def __init__(self, oracle: str) -> None:
        found = shutil.which(oracle)
        if found is None:
            raise GuardOracleError(f"no guard oracle at {oracle}")
        # What judged, taken before it runs: the launcher and the assemblies beside it (a .NET apphost is only a launcher).
        self.identity = {"path": found, **{p.name: run_meta.sha256_file(p) for p in sorted(
            [Path(found), *Path(found).parent.glob("Baxy.*.dll")])}}
        self._process = subprocess.Popen([found], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                         encoding="utf-8", bufsize=1)

    def _ask(self, request: dict) -> dict:
        assert self._process.stdin is not None and self._process.stdout is not None
        try:
            self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
            line = self._process.stdout.readline()
            answer = json.loads(line) if line else None
        except (OSError, ValueError) as exc:
            raise GuardOracleError(f"the guard oracle failed ({exc!r})") from exc
        if not isinstance(answer, dict):
            raise GuardOracleError(f"the guard oracle answered {line!r} (exit {self._process.poll()})")
        return answer

    def _state(self, request: dict) -> None:
        if (answer := self._ask(request)) != {}:
            raise GuardOracleError(f"the guard oracle answered {answer!r} to {list(request)}")

    def reset(self) -> None:
        self._state({"reset": True})

    def heard(self, words: str, answering: bool = False) -> None:
        self._state({"heard": words, "answering": answering})

    def asked(self) -> None:
        self._state({"asked": True})

    def call(self, operation: str, arguments: dict | None) -> dict:
        answer = self._ask({"call": operation, "arguments": arguments or {}})
        if isinstance(answer.get("refused"), str) != (not isinstance(answer.get("operation"), str)) \
                or ("operation" in answer and not isinstance(answer.get("arguments"), dict)):
            raise GuardOracleError(f"the guard oracle answered {answer!r} to a call")
        return answer

    def ran(self, operation: str, arguments: dict | None, observation: str) -> None:
        self._state({"ran": operation, "arguments": arguments or {}, "observation": observation})

    def close(self) -> None:
        if self._process.poll() is None:
            assert self._process.stdin is not None
            self._process.stdin.close()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()  # its own child, by its handle


def person_words(conversation: list) -> list[str]:
    """The person's words in a conversation as the mind keeps it: their messages (no note of BAXY's «[...]») and their
    answers to the model's questions (ask_user's results), in order."""
    asked, words = set(), []
    for message in conversation:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if message.get("role") == "user" and isinstance(content, str) and not content.startswith(NOTE):
            words.append(content)
        elif message.get("role") == "tool" and message.get("tool_call_id") in asked and isinstance(content, str):
            words.append(content)
        asked |= {c.get("id") for c in message.get("tool_calls") or []
                  if (c.get("function") or {}).get("name") == ASK_USER}
    return words


def refusal_code(observation: str) -> str:
    """The code of a refusal the oracle gave (its «error», else its «status»)."""
    try:
        facts = json.loads(observation)
    except (TypeError, ValueError):
        return "?"
    return str(facts.get("error") or facts.get("code") or facts.get("status") or "?") if isinstance(facts, dict) else "?"


class Seen(NamedTuple):
    """A turn after the guards: the decision the person sees, the calls that went, the refusals' codes, the turn's last
    result, and the mind's failure on the way (None)."""
    shown: dict
    went: list[str]
    refused: list[str]
    last: dict
    error: str | None = None


def seen(mind: Any, request_id: Any, first: dict, guards: Guards, limit: int,
         observe: Callable[[str, dict | None, int], str] | None = None) -> Seen:
    """The turn from its first decision as the App runs it, up to `limit` calls: each call through the guards, a refused
    one back to the model with its refusal. The decision the person sees is the first call that goes, as it would run,
    or the model's words; a call still unruled when the calls are spent is none of them («unfinished»). With `observe`
    (op, arguments, index → the call's result) the turn goes on after a call goes, as the session bench closes it;
    without it, it stops there. The oracle's failures stop the run (GuardOracleError); the mind's end the turn."""
    if first.get("unsure"):
        # A call the mind doubted is held for the person before the App's guards (NativeTurnLoop: UnsureHeld): they see
        # that call, asked.
        return Seen(first, [], [], first)
    result, decision, went, refused, calls = first, None, [], [], 0
    try:
        while result.get("kind") == "action" and calls < limit:
            calls += 1
            op = str(result.get("operation"))
            ruling = guards.call(op, result.get("arguments"))
            if "refused" in ruling:
                refused.append(refusal_code(ruling["refused"]))
                observation = ruling["refused"]
            else:
                ran = {"kind": "action", "operation": ruling["operation"], "arguments": ruling["arguments"]}
                decision = decision or ran
                went.append(ran["operation"])
                if observe is None:
                    return Seen(decision, went, refused, result)
                observation = observe(ran["operation"], ran["arguments"], calls)
                guards.ran(ran["operation"], ran["arguments"], observation)
            result = mind.continue_turn(request_id, observation, final=calls == limit)
    except GuardOracleError:
        raise
    except Exception as exc:  # noqa: BLE001 - the mind failed after the first decision: the turn ends there
        return Seen(decision or {"kind": "error"}, went, refused, {"kind": "error"}, repr(exc)[:200])
    if result.get("kind") == "clarify":  # the App's «question» step (NetworkEgress.Asked)
        guards.asked()
    unfinished = {"kind": "unfinished"} if result.get("kind") == "action" else result
    return Seen(decision or unfinished, went, refused, result)


def seen_summary(counted: list[dict], guards: Guards | None) -> dict:
    """The run's second number, beside its «ok»: the decisions the person sees, and the oracle that judged them."""
    if guards is None:
        return {}
    ok = sum(bool(r.get("ok_seen")) for r in counted)
    return {"ok_seen": ok, "accuracy_seen": round(ok / max(1, len(counted)), 4), "guardas": guards.identity,
            "refused": sum(bool(r.get("refused")) for r in counted),
            "seen_errors": [r["id"] for r in counted if r.get("seen_error")]}
