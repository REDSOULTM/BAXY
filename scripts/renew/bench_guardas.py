"""The App's guards for the decision benches (C62): what the person sees, beside the model's first decision.

bench_decision and bench_sesion_larga judge the mind's first decision of a turn. In the App that call goes first through
its shape guards (NativeTurnLoop: NetworkEgress.Unsaid, SaidFolders, SaidApplication, SaidVerbs), which refuse it and
send it back to the model with what to do next, or route it into the folder or the app the person named: V6D278's
filesystem_list and FER022's message.draft were wrong first decisions the App never runs. With --guardas the benches
also judge the decision the person sees: each call through the App's own guards (the oracle, tests/Baxy.GuardOracle,
never a copy of them here), a refused one back to the model with the App's refusal, until a call goes (as it would run)
or the model answers in words. The first decision stays the bench's number, as before; the one seen is the second.

Oracle protocol, one JSON object per line each way: {"heard": words, "answering": bool} → {}; {"asked": true} → {};
{"call": op, "arguments": {...}} → {"refused": observation} or {"operation": op, "arguments": {...}, "note": ...,
"held": NetworkEgress.Holds' cause or null}; {"ran": op, "arguments": {...}, "observation": text} → {"observation": the
result as the model reads it, with the call's said note}; {"reset": true} → {}. Any other answer stops the run
(GuardOracleError): a run that went on without its guards would report first decisions as the ones seen.
"""
import subprocess
import json
import pathlib
import typing

import run_meta

# The note the mind adds to the person's words starts so (the clock, a pending call, a cut): never their words (Mind._said).
NOTE = "["
ASK_USER = "ask_user"


class GuardOracleError(RuntimeError):
    """The oracle died or answered out of its protocol: the run stops."""


class Guards:
    """The oracle's process for one run: the executable `oracle`, closed by close()."""

    def __init__(self, oracle: str) -> None:
        # A full path, never a name looked up (Windows looks in the current folder first).
        if not (pathlib.Path(oracle).is_absolute() and pathlib.Path(oracle).is_file()):
            raise GuardOracleError(f"no guard oracle at {oracle}")
        found = str(pathlib.Path(oracle))
        # What judged, taken before it runs: the launcher and the assemblies beside it (a .NET apphost is only a launcher).
        self.identity = {"path": found, **{p.name: run_meta.sha256_file(p) for p in sorted(
            [pathlib.Path(found), *pathlib.Path(found).parent.glob("Baxy*.dll")])}}
        self._process = subprocess.Popen([found], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                         encoding="utf-8", bufsize=1)

    def _ask(self, request: dict) -> dict:
        into, out = self._process.stdin, self._process.stdout
        assert into and out
        try:
            print(json.dumps(request, ensure_ascii=False), file=into, flush=True)
            line = out.readline()
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

    def ran(self, operation: str, arguments: dict | None, observation: str) -> str:
        """The call's result as the model reads it in the App: with the said note of the call (NativeTurnLoop.WithSaid)."""
        answer = self._ask({"ran": operation, "arguments": arguments or {}, "observation": observation})
        if set(answer) != {"observation"} or not isinstance(answer["observation"], str):
            raise GuardOracleError(f"the guard oracle answered {answer!r} to a result")
        return answer["observation"]

    def close(self) -> None:
        if self._process.poll() is None and self._process.stdin:
            self._process.stdin.close()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Its own child, by its handle.
                self._process.kill()


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
    except ValueError:
        return "?"
    return str(facts.get("error") or facts.get("code") or facts.get("status") or "?") if isinstance(facts, dict) else "?"


class Seen(typing.NamedTuple):
    """A turn after the guards: the decision the person sees, the calls that went, the refusals' codes, the turn's last
    result, the mind's failure on the way (None), and the causes the App held calls that went by for the person's «sí»
    (NetworkEgress.Holds: the person sees the call, asked; the session bench still gives it a result)."""
    shown: dict
    went: list[str]
    refused: list[str]
    last: dict
    error: str | None = None
    held: list[str] = []


def seen(mind: typing.Any, request_id: typing.Any, first: dict, guards: Guards, limit: int,
         observe: typing.Callable[[str, dict | None, int], str] | None = None) -> Seen:
    """The turn from its first decision as the App runs it, up to `limit` calls: each call through the guards, a refused
    one back to the model with its refusal. The decision the person sees is the first call that goes, as it would run,
    or the model's words; a call still unruled when the calls are spent is none of them («unfinished»). With `observe`
    (op, arguments, index → the call's result) the turn goes on after a call goes, as the session bench closes it;
    without it, it stops there. The oracle's failures stop the run (GuardOracleError); the mind's end the turn."""
    result, decision, went, refused, held, calls = first, None, [], [], [], 0
    try:
        while result.get("kind") == "action" and calls < limit:
            if result.get("unsure"):
                # A call the mind doubted, first or after a refusal, is held for the person before the App's guards
                # (NativeTurnLoop.DriveAsync checks it at every step: UnsureHeld): they see that call, asked.
                return Seen(decision or result, went, refused, result, None, held)
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
                if ruling.get("held"):
                    held.append(str(ruling["held"]))
                if observe is None:
                    return Seen(decision, went, refused, result, None, held)
                observation = guards.ran(ran["operation"], ran["arguments"],
                                         observe(ran["operation"], ran["arguments"], calls))
            result = mind.continue_turn(request_id, observation, final=calls == limit)
    except GuardOracleError:
        raise
    except Exception as failure:  # noqa: BLE001 - the mind failed after the first decision: the turn ends there
        return Seen(decision or {"kind": "error"}, went, refused, {"kind": "error"}, repr(failure)[:200], held)
    if result.get("kind") == "clarify":  # the App's «question» step (NetworkEgress.Asked)
        guards.asked()
    unfinished = {"kind": "unfinished"} if result.get("kind") == "action" else result
    return Seen(decision or unfinished, went, refused, result, None, held)


def seen_summary(counted: list[dict], guards: Guards | None) -> dict:
    """The run's second number, beside its «ok»: the decisions the person sees, and the oracle that judged them."""
    if guards is None:
        return {}
    ok = sum(bool(r.get("ok_seen")) for r in counted)
    return {"ok_seen": ok, "accuracy_seen": round(ok / max(1, len(counted)), 4), "guardas": guards.identity,
            "refused": sum(bool(r.get("refused")) for r in counted),
            "seen_errors": [r["id"] for r in counted if r.get("seen_error")]}
