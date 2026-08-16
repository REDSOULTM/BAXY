"""Replay every exact historical runtime message through the real mind sidecar.

The gate starts the same persistent ``baxy-mind`` process and local GGUF used
by the desktop app, configures it with the compiled core catalog, and sends one
isolated ``turn.decide`` request for every exact runtime case.  The turn result
is the sole routing decision and conversational response.  A ``plan`` request
is sent only when that result has kind ``plan``.  No operation is dispatched
to the core, so this is a full decision/planner replay without physical side
effects.

Results are appended durably after every case and are safe to resume.
"""

from __future__ import annotations

import argparse
import atexit
import ctypes
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    RuntimeConfig,
    add_runtime_arguments,
    resolve_runtime_from_args_or_error,
)
from scripts.build_layout import load_build_layout  # noqa: E402

SRC = REPO / "src"
RUNTIME_CONFIG_SOURCE = REPO / "scripts" / "baxy_runtime_config.py"
LEDGER = REPO / "artifacts" / "historical_exhaustive"
CASES = LEDGER / "all_executable_cases.jsonl"
ORACLE = LEDGER / "runtime_oracle.jsonl"
LANGUAGE_SCOPE = LEDGER / "runtime_language_scope.jsonl"
OUTPUT = LEDGER / "runtime_model_gate.jsonl"
SUMMARY = LEDGER / "runtime_model_gate_summary.json"
APP_ROUTES = LEDGER / "runtime_app_route_gate.jsonl"
BUILD_LAYOUT = load_build_layout(REPO)
CORE = BUILD_LAYOUT.core_executable(REPO)

FAMILY_ALIASES = {
    "capture": "vision",
    "computer": "computer_use",
    "computer_use": "computer_use",
    "game": "game",
    "media": "media",
    "message": "message",
    "note": "note_task",
    "ocr": "vision",
    "office": "office",
    "peripheral": "peripheral",
    "reminder": "notification",
    "streaming": "media",
    "system": "system",
    "settings": "system_settings",
    "task": "note_task",
    "wifi": "network",
}

HARD_FAILURE_STATUSES = frozenset({
    "false_effect",
    "invalid_conversation",
    "irrelevant_conversation",
    "missed_conversation",
    "missed_operation",
    "runtime_error",
    "wrong_operation",
})


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def is_runtime(case: dict[str, Any]) -> bool:
    return any(
        str(value).startswith("runtime_")
        for value in case.get("provenance_classes") or ()
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint(
    oracle: Path,
    app_routes: Path,
    language_scope: Path = LANGUAGE_SCOPE,
) -> str:
    digest = hashlib.sha256()
    sources = sorted((SRC / "baxy_mind").glob("*.py")) + [
        SRC / "baxy_mind" / "data" / "historical_runtime_intents.jsonl",
        RUNTIME_CONFIG_SOURCE,
        Path(__file__).resolve(),
        CORE,
        oracle,
        language_scope,
    ]
    for path in sources:
        digest.update(str(path.relative_to(REPO)).encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    digest.update(str(app_routes.relative_to(REPO)).encode("utf-8"))
    digest.update(b"\0")
    with app_routes.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            route = {
                key: row.get(key)
                for key in ("CaseId", "TextSha256", "Decision", "Operation", "Status")
            }
            digest.update(
                json.dumps(
                    route,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            digest.update(b"\n")
    digest.update(b"\0")
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def core_capabilities() -> list[dict[str, Any]]:
    if not CORE.is_file():
        raise FileNotFoundError(f"compiled core not found: {CORE}")
    environment = os.environ.copy()
    environment["BAXY_DATA_DIR"] = str(
        Path(environment["LOCALAPPDATA"])
        / "BAXY"
        / ("core-model-gate-" + uuid.uuid4().hex)
    )
    process = subprocess.Popen(
        [str(CORE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    try:
        assert process.stdout is not None
        line = process.stdout.readline()
        if not line:
            error = process.stderr.read() if process.stderr is not None else ""
            raise RuntimeError("core did not emit hello: " + error[-2000:])
        hello = json.loads(line)
        return [
            {
                key: capability[key]
                for key in ("name", "description", "argumentsSchema", "risk")
            }
            for capability in hello["capabilities"]
        ]
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.wait(timeout=20)


class MindClient:
    def __init__(
        self,
        capabilities: list[dict[str, Any]],
        runtime: RuntimeConfig,
        endpoint: str | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._runtime = runtime
        self._endpoint = endpoint
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._stderr_tail: list[str] = []
        try:
            self._start()
        except BaseException:
            self.close()
            raise

    def _start(self) -> None:
        if self._endpoint is None:
            if not self._runtime.gguf.is_file():
                raise FileNotFoundError(f"GGUF not found: {self._runtime.gguf}")
            if not self._runtime.llama_server.is_file():
                raise FileNotFoundError(
                    f"llama-server not found: {self._runtime.llama_server}"
                )
        environment = os.environ.copy()
        existing_python_path = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = str(self._runtime.python_path) + (
            os.pathsep + existing_python_path if existing_python_path else ""
        )
        environment["PYTHONUTF8"] = "1"
        environment["BAXY_MIND_LLM_GGUF"] = str(self._runtime.gguf)
        environment["BAXY_MIND_LLAMA_SERVER"] = str(
            self._runtime.llama_server
        )
        environment["BAXY_MIND_NGL"] = str(self._runtime.gpu_layers)
        environment["BAXY_MIND_CTX"] = "4096"
        environment["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = "55"
        if self._endpoint is not None:
            environment["BAXY_MIND_LLM_ENDPOINT"] = self._endpoint
        else:
            environment.pop("BAXY_MIND_LLM_ENDPOINT", None)
        self._process = subprocess.Popen(
            [str(self._runtime.python), "-u", "-m", "baxy_mind"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            cwd=REPO,
            bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        # Loading the multilingual router precedes hello and is intentionally
        # excluded from per-message latency.  A cold Windows cache can take
        # considerably longer than a normal desktop turn.
        hello = self._next(180)
        if hello.get("type") != "hello":
            raise RuntimeError(f"mind did not emit hello: {hello}")
        ready = self.request(
            {
                "type": "catalog.configure",
                "id": "catalog",
                "capabilities": self._capabilities,
            },
            timeout=180,
            expected_type="catalog.ready",
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError(f"mind rejected catalog: {ready}")

    def _read_stdout(self) -> None:
        try:
            process = self._process
            assert process is not None and process.stdout is not None
            for line in process.stdout:
                if not line.strip():
                    continue
                self._messages.put(json.loads(line))
        except BaseException as error:  # noqa: BLE001
            self._messages.put(error)

    def _read_stderr(self) -> None:
        process = self._process
        assert process is not None and process.stderr is not None
        for line in process.stderr:
            self._stderr_tail.append(line.rstrip())
            if len(self._stderr_tail) > 100:
                del self._stderr_tail[:50]

    def _next(self, timeout: float) -> dict[str, Any]:
        try:
            result = self._messages.get(timeout=timeout)
        except queue.Empty as error:
            process = self._process
            code = process.poll() if process is not None else None
            tail = "\n".join(self._stderr_tail[-20:])
            raise TimeoutError(
                f"mind reply timed out (exit={code})\n{tail}"
            ) from error
        if isinstance(result, BaseException):
            raise result
        return result

    def request(
        self,
        message: dict[str, Any],
        timeout: float = 75,
        *,
        expected_type: str | None = None,
    ) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None or process.poll() is not None:
            raise RuntimeError("mind process is not running")
        process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        process.stdin.flush()
        request_id = message.get("id")
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"mind request {request_id} timed out")
            reply = self._next(remaining)
            if reply.get("id") == request_id:
                reply_type = str(reply.get("type") or "")
                if reply_type == "error":
                    raise RuntimeError(
                        "mind request failed: "
                        f"{reply.get('code') or 'unknown'}: "
                        f"{reply.get('message') or 'no message'}"
                    )
                if expected_type is not None and reply_type != expected_type:
                    raise RuntimeError(
                        f"mind request {request_id} returned {reply_type!r}; "
                        f"expected {expected_type!r}"
                    )
                return reply

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None and process.stdin is not None:
            try:
                process.stdin.write(
                    json.dumps({"type": "shutdown", "id": "shutdown"}) + "\n"
                )
                process.stdin.flush()
                process.wait(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()

    def __enter__(self) -> MindClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def operation_family(operation: str) -> str:
    prefix = operation.split(".", 1)[0]
    return FAMILY_ALIASES.get(prefix, prefix)


def operation_families(operation: str) -> set[str]:
    if operation == "clipboard.paste":
        return {"clipboard", "input"}
    return {operation_family(operation)}


_BAD_CONVERSATION_REPLIES = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bnecesito un dato m[aá]s para producir un plan\b",
        r"\bno pude construir un plan completo\b",
        r"\blos argumentos (?:de|del) step\b",
        r"\bplan contiene operaciones sin evidencia\b",
        r"\b[a-z][a-z0-9_]*\s*\([^\n]{0,200}\b(?:query|action|provider|target)\s*=",
    )
)


def conversation_quality(text: str, reply: str) -> str | None:
    """Identify hard turn-response failures without model self-judgment."""

    value = reply.strip()
    if not value:
        return "invalid_conversation"
    if any(pattern.search(value) for pattern in _BAD_CONVERSATION_REPLIES):
        return "irrelevant_conversation"
    if value.casefold() == text.strip().casefold():
        return "irrelevant_conversation"
    return None


def semantic_operation_failure(
    text: str,
    plan: dict[str, Any],
    *,
    compare_arguments: bool = True,
) -> str | None:
    """Reject known physical intents that merely share a broad operation family."""

    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(character for character in folded if not unicodedata.combining(character))
    folded = " ".join(folded.strip(" .!?¿¡\"'").split())
    steps = [
        (str(step.get("operation") or ""), step.get("arguments") or {})
        for step in plan.get("steps") or []
    ]

    def exactly(expected: list[tuple[str, dict[str, Any]]]) -> bool:
        if compare_arguments:
            return steps == expected
        return [operation for operation, _ in steps] == [
            operation for operation, _ in expected
        ]

    if re.fullmatch(
        r"(?:mueve|move) (?:el |the )?(?:mouse|raton|pointer) (?:al |to the )?"
        r"(?:centro|center)(?: (?:de|of) (?:la |the )?(?:pantalla|screen))?",
        folded,
    ):
        return None if exactly([
            ("input.pointer.control", {"action": "move_center"}),
        ]) else "wrong_operation"
    if re.fullmatch(r"(?:haz |make )?(?:mouse )?click (?:ahi|there)(?: fast| rapido)?", folded):
        return None if exactly([
            ("input.pointer.control", {"action": "click"}),
        ]) else "wrong_operation"
    if re.fullmatch(r"(?:haz|make) scroll (?:hacia )?(?:abajo|down)", folded):
        return None if exactly([
            ("input.pointer.control", {"action": "scroll_down"}),
        ]) else "wrong_operation"
    if re.fullmatch(
        r"(?:presiona|aprieta|press|send) (?:la |the )?"
        r"(?:combinacion |hotkey )?(?:control|ctrl)[ +]shift[ +](?:escape|esc)",
        folded,
    ):
        return None if exactly([
            ("input.key.press", {"key": "ctrl_shift_escape"}),
        ]) else "wrong_operation"
    if re.fullmatch(
        r"(?:type|press|presiona) (?:the |la )?(?:key |tecla )?"
        r"(?:escape|esc)(?: key)? (?:and then|then|y luego) "
        r"(?:press )?(?:the |la )?(?:win|windows)(?: key| tecla)?",
        folded,
    ):
        return None if exactly([
            ("input.key.press", {"key": "escape"}),
            ("input.key.press", {"key": "win"}),
        ]) else "wrong_operation"
    if re.fullmatch(r"(?:(?:que|cual) (?:mouse|raton) (?:tengo|esta conectado)|what mouse do i have)", folded):
        return None if exactly([
            ("peripheral.list", {"kind": "mouse"}),
        ]) else "wrong_operation"
    if re.fullmatch(r"(?:(?:que|cual) teclado (?:tengo|esta conectado)|which keyboard is connected)", folded):
        return None if exactly([
            ("peripheral.list", {"kind": "keyboard"}),
        ]) else "wrong_operation"
    exact_cases: list[tuple[str, list[tuple[str, dict[str, Any]]]]] = [
        (r"(?:presiona|aprieta|press) (?:la )?(?:combinacion )?alt[ +]tab",
         [("input.key.press", {"key": "alt_tab"})]),
        (r"(?:abre|open) (?:el )?(?:menu contextual|context menu)",
         [("input.key.press", {"key": "context_menu"})]),
        (r"(?:pega|paste) (?:el )?(?:texto )?(?:del |from the )?(?:portapapeles|clipboard)",
         [("clipboard.paste", {})]),
        (r"(?:recarga|actualiza|reload|refresh) (?:la |the )?(?:pagina|page) actual",
         [("browser.control", {"action": "reload"})]),
        (r"(?:pon|pone|coloca|set|put) (?:el |the )?(?:video )?(?:en |in )?"
         r"(?:pantalla completa|fullscreen)(?: (?:el |the )?video)?",
         [("browser.control", {"action": "fullscreen_video"})]),
        (r"(?:abre|open) (?:el |the )?(?:teclado|on screen keyboard)(?:,? por favor| please)?",
         [("input.keyboard.open", {})]),
    ]
    for pattern, expected in exact_cases:
        if re.fullmatch(pattern, folded):
            return None if exactly(expected) else "wrong_operation"
    if re.fullmatch(r"(?:dame|dime|show me|tell me) (?:el )?layout(?: ahora| now)?", folded):
        return None if exactly([
            ("input.keyboard.status", {}),
        ]) else "wrong_operation"
    if re.fullmatch(r"dame las notas", folded):
        return None if exactly([
            ("note.list", {}),
        ]) else "wrong_operation"
    fixed_relative_cases = {
        "sube el volumen": [("audio.volume.adjust", {"direction": "up", "amount": 10})],
        "baja el volumen un poco, por favor": [("audio.volume.adjust", {"direction": "down", "amount": 5})],
        "turn up the system volume please": [("audio.volume.adjust", {"direction": "up", "amount": 10})],
        "baja bastante el brillo": [("system.settings.adjust", {"setting": "brightness", "direction": "down", "amount": 15})],
        "subi el volumen y baja el brillo": [
            ("audio.volume.adjust", {"direction": "up", "amount": 10}),
            ("system.settings.adjust", {"setting": "brightness", "direction": "down", "amount": 10}),
        ],
        "conecta al wifi galaxy": [("wifi.connect.named", {"profileName": "galaxy"})],
        "connect to wifi network casared": [("wifi.connect.named", {"profileName": "casared"})],
        "instala doom eternal en steam": [("game.install.named", {"title": "doom eternal"})],
        "open steam and install stardew valley": [("game.install.named", {"title": "stardew valley"})],
    }
    if folded in fixed_relative_cases:
        return None if exactly(fixed_relative_cases[folded]) else "wrong_operation"
    if re.fullmatch(
        r"(?:(?:usa|use) (?:el |the )?(?:idioma|keyboard layout|layout) "
        r"(?:del teclado )?(?:para |for )?(?:espanol|spanish)|"
        r"cambia (?:el )?idioma (?:del )?teclado(?: a espanol)?|cambia idioma teclado)",
        folded,
    ):
        return None if exactly([
            ("input.keyboard.layout", {"language": "spanish"}),
        ]) else "wrong_operation"
    if re.search(r"\b(?:microfono|microphone|mic)\b", folded) and re.search(
        r"\b(?:mute|mutea|silencia|unmute|volumen|volume)\b", folded
    ):
        expected_state = not bool(re.search(
            r"\b(?:unmute|reactiva|activa|desmutea)\b", folded
        ))
        return None if exactly([
            ("audio.microphone.mute", {"state": expected_state}),
        ]) else "wrong_operation"
    if re.search(r"\b(?:escaner|escaneres|scanner|scanners)\b", folded) and re.search(
        r"\b(?:disponibles|available|tienes|tengo|lista|list)\b", folded
    ):
        return None if exactly([
            ("peripheral.list", {"kind": "scanner"}),
        ]) else "wrong_operation"
    return None


def assess(
    oracle: dict[str, Any],
    turn: dict[str, Any],
    plan: dict[str, Any] | None,
    text: str = "",
) -> tuple[str, list[str]]:
    turn_kind = turn.get("kind")
    if turn.get("type") == "error":
        return "runtime_error", []
    if turn.get("type") != "turn.result" or turn_kind not in {
        "action",
        "clarify",
        "conversation",
        "plan",
    }:
        return "runtime_error", []
    if turn_kind == "action":
        operation = str(turn.get("operation") or "")
        if not operation:
            return "runtime_error", []
        steps = [{"operation": operation, "arguments": None}] if operation else []
        outcome = turn
    elif turn_kind == "plan":
        if (
            plan is None
            or plan.get("type") == "error"
            or plan.get("type") != "plan.result"
        ):
            return "runtime_error", []
        steps = list(plan.get("steps") or [])
        outcome = plan
    else:
        steps = []
        outcome = turn
    operations = [
        str(step.get("operation") or "")
        for step in steps
        if step.get("operation")
    ]
    actual_families = sorted({
        family for value in operations for family in operation_families(value)
    })
    expected_effect = oracle["expected_effect"]
    expected_families = set(oracle.get("expected_families") or ())
    compatible_expected = set(expected_families)
    compatibility = {
        "browser": {"browser", "web"},
        "media": {"media", "streaming"},
        "note_task": {"note", "task"},
        "network": {"network", "system_settings"},
        "system_settings": {"network", "system"},
        "vision": {"capture", "ocr", "vision"},
        "web": {"browser", "web"},
    }
    for family in expected_families:
        compatible_expected.update(compatibility.get(family, ()))
    kind = outcome.get("kind")
    semantic_failure = semantic_operation_failure(
        text,
        {"steps": steps},
        compare_arguments=turn_kind != "action",
    )
    if semantic_failure is not None:
        return semantic_failure, actual_families
    if kind == "conversation" and (
        turn_kind != "conversation" or turn.get("operation")
    ):
        return "invalid_conversation", actual_families
    if kind == "conversation":
        quality_failure = conversation_quality(
            text,
            str(turn.get("reply") or ""),
        )
        if quality_failure is not None:
            return quality_failure, actual_families
    if expected_effect == "none":
        if kind == "conversation":
            return "pass_no_effect", actual_families
        if kind == "clarify" and str(outcome.get("question") or "").strip():
            return "pass_safe_clarification", actual_families
        return "false_effect", actual_families
    if expected_effect == "unsupported":
        return (
            "pass_no_effect" if kind in {"conversation", "clarify"} else "false_effect"
        ), actual_families
    if expected_effect == "operation":
        if kind in {"action", "plan"} and compatible_expected.intersection(
            actual_families
        ):
            return "pass_operation_family", actual_families
        if kind == "clarify":
            return "review_clarification", actual_families
        return "missed_operation", actual_families
    if kind == "clarify" and str(outcome.get("question") or "").strip():
        return "pass_safe_clarification", actual_families
    return "review_unresolved_oracle", actual_families


def request_turn_and_optional_plan(
    mind: MindClient,
    request_id: str,
    text: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, float, float]:
    """Run the desktop semantic sequence without dispatching any operation."""

    before_turn = time.monotonic()
    turn = mind.request(
        {"type": "turn.decide", "id": request_id, "text": text},
        timeout=22,
        expected_type="turn.result",
    )
    turn_seconds = time.monotonic() - before_turn
    plan = None
    plan_seconds = 0.0
    if turn.get("kind") == "plan":
        before_plan = time.monotonic()
        plan = mind.request(
            {"type": "plan", "id": request_id + "_plan", "text": text},
            timeout=60,
            expected_type="plan.result",
        )
        plan_seconds = time.monotonic() - before_plan
    return turn, plan, turn_seconds, plan_seconds


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(row["case_id"])
        for row in read_jsonl(path)
        if row.get("case_id") and row.get("completed") is True
    }


def append_result(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def process_exists(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            process_query_limited_information,
            False,
            process_id,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        return True
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def process_start_time(process_id: int) -> float | None:
    """Return a stable process-creation token when the platform exposes one."""

    if process_id <= 0:
        return None
    if os.name == "nt":
        process_query_limited_information = 0x1000

        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            process_query_limited_information,
            False,
            process_id,
        )
        if not handle:
            return None
        try:
            created = FileTime()
            exited = FileTime()
            kernel = FileTime()
            user = FileTime()
            ok = ctypes.windll.kernel32.GetProcessTimes(  # type: ignore[attr-defined]
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
            if not ok:
                return None
            ticks = (int(created.high) << 32) | int(created.low)
            return ticks / 10_000_000 - 11_644_473_600
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
    try:
        return float((Path("/proc") / str(process_id)).stat().st_ctime_ns)
    except OSError:
        return None


def lock_owner_is_live(lock: Path, raw_owner: str) -> bool:
    """Reject stale locks even when the operating system has reused their PID."""

    try:
        parsed = json.loads(raw_owner)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        try:
            process_id = int(parsed["pid"])
            expected_start = float(parsed["started"])
        except (KeyError, TypeError, ValueError):
            return False
        observed_start = process_start_time(process_id)
        return observed_start is not None and abs(observed_start - expected_start) < 0.01
    try:
        process_id = int(raw_owner.strip())
    except ValueError:
        return False
    if not process_exists(process_id):
        return False
    # Migration from the old PID-only lock: a process created after the lock
    # cannot be its owner, even when Windows recycled the numeric PID.
    observed_start = process_start_time(process_id)
    if observed_start is not None and os.name == "nt":
        try:
            return observed_start <= lock.stat().st_mtime + 1.0
        except OSError:
            return False
    return True


def acquire_run_lock(output: Path) -> Path:
    """Prevent two model replays from corrupting the same evidence ledger."""
    lock = output.with_suffix(output.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = lock.read_text(encoding="ascii").strip()
            except OSError:
                owner = ""
            if not lock_owner_is_live(lock, owner):
                if attempt == 0:
                    lock.unlink(missing_ok=True)
                    continue
            raise RuntimeError(
                f"model gate already owns {output} (pid={lock.read_text(encoding='ascii').strip()})"
            )
        identity = json.dumps(
            {"pid": os.getpid(), "started": process_start_time(os.getpid())},
            sort_keys=True,
            separators=(",", ":"),
        )
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(identity)

        def release() -> None:
            try:
                if lock.read_text(encoding="ascii").strip() == identity:
                    lock.unlink(missing_ok=True)
            except OSError:
                pass

        atexit.register(release)
        return lock
    raise RuntimeError(f"could not acquire model gate lock: {lock}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--oracle", type=Path, default=ORACLE)
    parser.add_argument("--language-scope", type=Path, default=LANGUAGE_SCOPE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY)
    parser.add_argument("--app-routes", type=Path, default=APP_ROUTES)
    add_runtime_arguments(parser)
    parser.add_argument(
        "--ngl",
        dest="gpu_layers",
        type=int,
        help="Alias compatible de --gpu-layers.",
    )
    parser.add_argument("--llm-endpoint")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--oracle-family",
        action="append",
        default=[],
        help="Select cases whose independent oracle expects this operation family.",
    )
    parser.add_argument(
        "--case-id-file",
        type=Path,
        help="UTF-8 text file containing one exact case id per line.",
    )
    parser.add_argument(
        "--replay-failures-from",
        type=Path,
        action="append",
        default=[],
        help="Select exact case ids whose prior gate status was a hard failure.",
    )
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    runtime = resolve_runtime_from_args_or_error(parser, args)

    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard index must be within a positive shard count")

    acquire_run_lock(args.output)
    if args.fresh and args.output.exists():
        args.output.unlink()
    oracle = {row["case_id"]: row for row in read_jsonl(args.oracle)}
    language_scope = {row["case_id"]: row for row in read_jsonl(args.language_scope)}
    cases = [case for case in read_jsonl(args.cases) if is_runtime(case)]
    if set(oracle) != {case["case_id"] for case in cases}:
        raise RuntimeError("runtime cases and independent oracle do not match exactly")
    if set(language_scope) != {case["case_id"] for case in cases}:
        raise RuntimeError("runtime cases and language scope do not match exactly")
    fingerprint = runtime_fingerprint(args.oracle, args.app_routes, args.language_scope)
    if args.output.exists() and any(
        row.get("runtime_fingerprint") != fingerprint
        for row in read_jsonl(args.output)
    ):
        raise RuntimeError(
            "model gate evidence belongs to another runtime; restart with --fresh"
        )
    completed = load_completed(args.output)
    app_routes = {
        str(row["CaseId"]): row for row in read_jsonl(args.app_routes)
    }
    if set(app_routes) != {case["case_id"] for case in cases}:
        raise RuntimeError("app route evidence and runtime cases do not match exactly")
    requested_ids = set(args.case_id)
    requested_families = set(args.oracle_family)
    if args.case_id_file is not None:
        requested_ids.update(
            line.strip()
            for line in args.case_id_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        unknown_requested = requested_ids.difference(oracle)
        if unknown_requested:
            raise ValueError(
                "unknown case ids in replay selection: "
                + ", ".join(sorted(unknown_requested)[:10])
            )
    for replay_path in args.replay_failures_from:
        requested_ids.update(
            str(row["case_id"])
            for row in read_jsonl(replay_path)
            if row.get("status") in HARD_FAILURE_STATUSES and row.get("case_id")
        )
        unknown_requested = requested_ids.difference(oracle)
        if unknown_requested:
            raise ValueError(
                "unknown case ids in failure replay selection: "
                + ", ".join(sorted(unknown_requested)[:10])
            )
    selected_ids = {
        case["case_id"]
        for index, case in enumerate(cases)
        if index % args.shard_count == args.shard_index
        and (not requested_ids or case["case_id"] in requested_ids)
        and (
            not requested_families
            or requested_families.intersection(oracle[case["case_id"]].get("expected_families") or [])
        )
    }
    for case in cases:
        request_id = case["case_id"]
        route = app_routes[request_id]
        if request_id in completed or request_id not in selected_ids:
            continue
        if language_scope[request_id]["scope"] == "out_of_scope_language":
            append_result(
                args.output,
                {
                    "case_id": request_id,
                    "text_sha256": case["text_sha256"],
                    "text_literal": case["text_literal"],
                    "completed": True,
                    "oracle_effect": oracle[request_id]["expected_effect"],
                    "oracle_families": oracle[request_id]["expected_families"],
                    "decision_kind": "out_of_scope_language",
                    "planner_kind": "",
                    "error_code": "",
                    "error_message": "",
                    "operations": [],
                    "plan_steps": [],
                    "actual_families": [],
                    "question": "",
                    "reply": "",
                    "turn_seconds": 0.0,
                    "plan_seconds": 0.0,
                    "total_seconds": 0.0,
                    "status": "out_of_scope_language",
                    "runtime_occurrence_count": case["occurrence_count"],
                    "tools_executed": 0,
                    "runtime_fingerprint": fingerprint,
                },
            )
            completed.add(request_id)
            continue
        decision = str(route.get("Decision") or "")
        expected_effect = oracle[request_id]["expected_effect"]
        if route.get("Status") == "pass_direct_operation_family":
            operation = str(route["Operation"])
            decision_kind = decision or "app_direct"
            operations = [operation]
            actual_families = sorted(operation_families(operation))
            question = ""
            status = "pass_app_direct_operation_family"
        elif decision == "direct_clarification":
            decision_kind = "clarify"
            operations = []
            actual_families = []
            question = (
                "Necesito que concretes el dato, alcance o confirmación "
                "antes de continuar; no ejecuté ningún efecto."
            )
            status = (
                "review_clarification"
                if expected_effect == "operation"
                else "pass_safe_clarification"
            )
        else:
            continue
        append_result(
            args.output,
            {
                "case_id": request_id,
                "text_sha256": case["text_sha256"],
                "text_literal": case["text_literal"],
                "completed": True,
                "oracle_effect": oracle[request_id]["expected_effect"],
                "oracle_families": oracle[request_id]["expected_families"],
                "decision_kind": decision_kind,
                "planner_kind": "",
                "error_code": "",
                "error_message": "",
                "operations": operations,
                "plan_steps": [
                    {"operation": operation, "arguments": None}
                    for operation in operations
                ],
                "actual_families": actual_families,
                "question": question,
                "reply": "",
                "turn_seconds": 0.0,
                "plan_seconds": 0.0,
                "total_seconds": 0.0,
                "status": status,
                "runtime_occurrence_count": case["occurrence_count"],
                "tools_executed": 0,
                "runtime_fingerprint": fingerprint,
            },
        )
        completed.add(request_id)
    pending = [
        case for case in cases
        if case["case_id"] in selected_ids and case["case_id"] not in completed
    ]
    if args.max_cases is not None:
        pending = pending[: max(0, args.max_cases)]
    started = time.monotonic()
    mind = (
        MindClient(
            core_capabilities(),
            runtime,
            args.llm_endpoint,
        )
        if pending
        else None
    )
    try:
        for position, case in enumerate(pending, 1):
            assert mind is not None
            request_id = case["case_id"]
            turn, plan, turn_seconds, plan_seconds = request_turn_and_optional_plan(
                mind,
                request_id,
                case["text_literal"],
            )
            status, actual_families = assess(
                oracle[request_id],
                turn,
                plan,
                case["text_literal"],
            )
            if turn.get("kind") == "action" and turn.get("operation"):
                operations = [turn["operation"]]
                plan_steps = [
                    {"operation": turn["operation"], "arguments": None}
                ]
            else:
                operations = [
                    step.get("operation")
                    for step in (plan or {}).get("steps") or []
                ]
                plan_steps = [
                    {
                        "operation": step.get("operation"),
                        "arguments": step.get("arguments"),
                        "depends_on": step.get("dependsOn") or [],
                    }
                    for step in (plan or {}).get("steps") or []
                ]
            outcome = plan if turn.get("kind") == "plan" and plan is not None else turn
            append_result(
                args.output,
                {
                    "case_id": request_id,
                    "text_sha256": case["text_sha256"],
                    "text_literal": case["text_literal"],
                    "completed": True,
                    "oracle_effect": oracle[request_id]["expected_effect"],
                    "oracle_families": oracle[request_id]["expected_families"],
                    "decision_kind": turn.get("kind") or turn.get("type"),
                    "planner_kind": (
                        plan.get("kind") or plan.get("type")
                        if plan is not None
                        else ""
                    ),
                    "error_code": str(outcome.get("code") or ""),
                    "error_message": str(outcome.get("message") or "")[:1000],
                    "operations": operations,
                    "plan_steps": plan_steps,
                    "actual_families": actual_families,
                    "question": str(outcome.get("question") or "")[:512],
                    "reply": str(turn.get("reply") or "")[:1000],
                    "turn_seconds": round(turn_seconds, 4),
                    "plan_seconds": round(plan_seconds, 4),
                    "total_seconds": round(turn_seconds + plan_seconds, 4),
                    "status": status,
                    "runtime_occurrence_count": case["occurrence_count"],
                    "tools_executed": 0,
                    "runtime_fingerprint": fingerprint,
                },
            )
            if position % 25 == 0 or position == len(pending):
                elapsed = time.monotonic() - started
                print(
                    json.dumps(
                        {
                            "completed_this_run": position,
                            "pending_this_run": len(pending) - position,
                            "latest_status": status,
                            "elapsed_seconds": round(elapsed, 1),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    finally:
        if mind is not None:
            mind.close()

    completed_rows = list(read_jsonl(args.output)) if args.output.exists() else []
    completed_ids = [str(row["case_id"]) for row in completed_rows]
    if len(completed_ids) != len(set(completed_ids)):
        raise RuntimeError("model gate evidence contains duplicate case IDs")
    rows_by_id = {row["case_id"]: row for row in completed_rows}
    statuses = Counter(row["status"] for row in rows_by_id.values())
    latencies = sorted(float(row["total_seconds"]) for row in rows_by_id.values())
    completed_selected = selected_ids.intersection(rows_by_id)
    complete_selected = completed_selected == selected_ids
    hard_failures = [
        row for row in rows_by_id.values()
        if row["status"] in HARD_FAILURE_STATUSES
    ]
    summary = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "every_exact_runtime_message_real_desktop_route_and_persistent_"
            "turn_decision_optional_plan_no_effect"
        ),
        "source_case_sha256": file_sha256(args.cases),
        "source_oracle_sha256": file_sha256(args.oracle),
        "source_language_scope_sha256": file_sha256(args.language_scope),
        "runtime_fingerprint": fingerprint,
        "unique_runtime_cases": len(cases),
        "target_language_cases": sum(
            row["scope"] == "target" for row in language_scope.values()),
        "out_of_scope_language_cases": sum(
            row["scope"] == "out_of_scope_language" for row in language_scope.values()),
        "selected_cases": len(selected_ids),
        "completed_cases": len(rows_by_id),
        "remaining_cases": len(selected_ids) - len(completed_selected),
        "runtime_occurrences_covered": sum(
            int(row["runtime_occurrence_count"]) for row in rows_by_id.values()
        ),
        "status_counts": dict(sorted(statuses.items())),
        "latency_seconds": {
            "maximum": max(latencies, default=0),
            "p50": latencies[len(latencies) // 2] if latencies else 0,
            "p95": latencies[int((len(latencies) - 1) * 0.95)] if latencies else 0,
        },
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "shard_completed": complete_selected,
        "all_cases_completed": (
            complete_selected
            and args.shard_count == 1
            and len(selected_ids) == len(cases)
        ),
        "hard_failures": len(hard_failures),
        "hard_failure_cases": [row["case_id"] for row in hard_failures[:100]],
        "tools_executed": 0,
    }
    write_json(args.summary_output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not complete_selected:
        return 2
    return 3 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
