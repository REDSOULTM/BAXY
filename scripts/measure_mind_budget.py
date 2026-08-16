"""Gate 12: presupuesto físico y latencia del runtime actual de BAXY.

La medición levanta el sidecar completo dos veces: primero con el número de
capas GPU registrado y después con ``-ngl 0``. En ambos perfiles usa únicamente
el protocolo público vigente:

* 30 ``turn.decide``;
* 10 ``arguments``;
* 5 ``narrate``.

No se ejecuta ninguna operación del catálogo. El core se abre sólo para leer
su catálogo autenticado. Las rutas del runtime proceden del manifiesto
registrado o de argumentos explícitos y nunca se copian al reporte público.

Salida predeterminada: ``artifacts/product/mind_budget_gate.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.baxy_runtime_config import (  # noqa: E402
    RuntimeConfig,
    add_runtime_arguments,
    public_runtime_identity,
    resolve_runtime as resolve_runtime,
    resolve_runtime_from_args,
)
from scripts.build_layout import BuildLayout, load_build_layout  # noqa: E402
from main import dotnet_executable, environment_for_dotnet  # noqa: E402

DEFAULT_OUTPUT = REPO / "artifacts" / "product" / "mind_budget_gate.json"
BUILD_LAYOUT = load_build_layout(REPO)


def default_core_candidates(
    repo: Path = REPO,
    layout: BuildLayout = BUILD_LAYOUT,
) -> tuple[Path, Path]:
    return (
        layout.core_executable(repo),
        layout.core_publish_executable(repo),
    )


DEFAULT_CORE_CANDIDATES = default_core_candidates()

GPU_VRAM_BUDGET_MIB = 3_072
CPU_VRAM_TOLERANCE_MIB = 128
CPU_RAM_BUDGET_MIB = 8 * 1_024
CPU_TURN_P50_BUDGET_SECONDS = 22.0
MIND_STARTUP_TRANSPORT_SLA_SECONDS = 120.0
EXPECTED_REQUESTS = 45

# El timeout HTTP llega a llama-server. El deadline exterior deja margen para
# serialización, validación de contratos e IPC, pero nunca supera la frontera
# real del shell. GPU conserva turn=22, arguments=20 y narrate=20. En CPU,
# turn/arguments mantienen sus fronteras interactivas, pero message.compose
# usa el contrato productivo autenticado de 120 s dentro de una ventana JSONL
# de 130 s; imponerle los 19 s de GPU medía otro producto.
PROFILE_LIMITS: dict[str, dict[str, float]] = {
    "gpu": {
        "handshake": MIND_STARTUP_TRANSPORT_SLA_SECONDS,
        "turn.decide": 22.0,
        "arguments": 20.0,
        "narrate": 20.0,
        "llm_http": 19.0,
        "shutdown": 15.0,
    },
    "cpu_fallback": {
        "handshake": MIND_STARTUP_TRANSPORT_SLA_SECONDS,
        "turn.decide": 22.0,
        "arguments": 20.0,
        "narrate": 130.0,
        "llm_http": 120.0,
        "shutdown": 15.0,
    },
}

TURN_TEXTS = (
    "che baxy fijate cuanta bateria le queda al notebook",
    "how much free space do I have left on disk",
    "pon el volumen de la compu al 30 por ciento",
    "mute everything please",
    "en cuanto esta el volumen ahora",
    "que gpu tiene este equipo",
    "cuanta vram se esta usando",
    "crea una nota que diga pagar el arriendo el viernes",
    "haz ping a example.com",
    "que hora es ahora",
    "lista los perfiles wifi guardados",
    "cuanta ram estoy usando ahora mismo",
    "dime la version de windows que tengo",
    "como anda la pc en general",
    "revisa cpu y ram juntos",
    "contame un chiste corto",
    "what do you think about pineapple on pizza",
    "abrime spotify y pone musica",
    "sube el volumen",
    "por que mi gpu no se usa",
    "gracias baxy, sos un capo",
    "make a note that says call the dentist tomorrow",
    "cuanto espacio libre queda en el disco",
    "esta cargando la bateria?",
    "is the sound muted right now",
    "esta conectado el wifi",
    "que no puedes hacer",
    "hola, todo bien?",
    "set the volume to seventy five percent",
    "cuantos nucleos tiene el procesador",
)
ARGUMENT_CASES = (
    ("audio.volume", "pon el volumen de la compu al 30 por ciento"),
    ("audio.volume", "set the volume to seventy five percent"),
    ("audio.mute", "mute everything please"),
    ("audio.mute", "quita el mute del audio"),
    ("note.create", "crea una nota que diga pagar el arriendo el viernes"),
    ("note.create", "make a note that says call the dentist tomorrow"),
    ("app.open", "abre la calculadora"),
    ("network.ping", "haz ping a example.com"),
    ("media.control", "pausa la música de Spotify"),
    ("system.settings.set", "pon el brillo al 40 por ciento"),
)
NARRATE_CASES = (
    (
        "crea una nota que diga pagar el arriendo",
        "note.create",
        {
            "succeeded": True,
            "verified": True,
            "title": "pagar el arriendo",
        },
    ),
    (
        "pon el volumen al 30",
        "audio.volume",
        {"succeeded": True, "verified": True, "level": 30},
    ),
    (
        "cuanta bateria queda",
        "system.status",
        {
            "succeeded": True,
            "verified": True,
            "battery_percent": 82,
            "charging": False,
        },
    ),
    (
        "mute the sound",
        "audio.mute",
        {"succeeded": True, "verified": True, "muted": True},
    ),
    (
        "how much disk space is left",
        "system.status",
        {"succeeded": True, "verified": True, "disk_free_gib": 324},
    ),
)

# Oracle semántico congelado para esta carga. La compuerta no compara prosa
# generada: valida únicamente identidad de intención, ausencia de efectos
# ajenos y argumentos literales autenticados.
TURN_EXPECTATIONS: tuple[tuple[str, object], ...] = (
    ("action", "system.status"),
    ("action", "system.status"),
    ("action", "audio.volume"),
    ("action", "audio.mute"),
    ("action", "audio.status"),
    ("action", "system.status"),
    ("action", "system.status"),
    ("action", "note.create"),
    ("action", "network.ping"),
    ("action", "system.time"),
    ("action", "wifi.profile.list"),
    ("action", "system.status"),
    ("action", "system.status"),
    ("action", "system.status"),
    ("action", "system.status"),
    ("conversation", None),
    ("conversation", None),
    ("clarify", "media.play.query"),
    ("clarify", "audio.volume.adjust"),
    ("conversation_or_action", "system.status"),
    ("conversation", None),
    ("action", "note.create"),
    ("action", "system.status"),
    ("action", "system.status"),
    ("action", "audio.status"),
    ("action", "wifi.status"),
    ("conversation", None),
    ("conversation", None),
    ("action", "audio.volume"),
    ("action", "system.status"),
)

ARGUMENT_EXPECTATIONS: tuple[tuple[dict[str, object], ...], ...] = (
    ({"level": 30},),
    ({"level": 75},),
    ({"state": True},),
    ({"state": False},),
    (
        {
            "title": "pagar el arriendo el viernes",
            "content": "pagar el arriendo el viernes",
        },
    ),
    (
        {
            "title": "call the dentist tomorrow",
            "content": "call the dentist tomorrow",
        },
    ),
    ({"appId": "calculadora"}, {"appId": "calculator"}),
    ({"host": "example.com"},),
    ({"action": "pause", "sourceApp": "spotify"},),
    ({"setting": "brightness", "value": 40},),
)


@dataclass(frozen=True)
class WorkItem:
    request_type: str
    case_id: str
    message: dict[str, Any]
    expected_reply_type: str


def build_workload() -> list[WorkItem]:
    if len(TURN_EXPECTATIONS) != len(TURN_TEXTS):
        raise AssertionError("cada turno debe tener un oráculo semántico")
    if len(ARGUMENT_EXPECTATIONS) != len(ARGUMENT_CASES):
        raise AssertionError("cada caso de argumentos debe tener un oráculo semántico")
    items: list[WorkItem] = []
    for index, text in enumerate(TURN_TEXTS):
        items.append(
            WorkItem(
                "turn.decide",
                f"turn-{index:02d}",
                {
                    "type": "turn.decide",
                    "id": f"turn-{index:02d}",
                    "text": text,
                    "history": [],
                },
                "turn.result",
            )
        )
    for index, (operation, text) in enumerate(ARGUMENT_CASES):
        items.append(
            WorkItem(
                "arguments",
                f"arguments-{index:02d}",
                {
                    "type": "arguments",
                    "id": f"arguments-{index:02d}",
                    "operation": operation,
                    "text": text,
                },
                "arguments.result",
            )
        )
    for index, (user_text, operation, outcome) in enumerate(NARRATE_CASES):
        items.append(
            WorkItem(
                "narrate",
                f"narrate-{index:02d}",
                {
                    "type": "narrate",
                    "id": f"narrate-{index:02d}",
                    "userText": user_text,
                    "operation": operation,
                    "outcome": outcome,
                },
                "narrate.result",
            )
        )
    if len(items) != EXPECTED_REQUESTS:
        raise AssertionError("la carga congelada debe contener 45 solicitudes")
    return items


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, int(len(ordered) * quantile))
    return ordered[index]


def latency_summary(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "p50": round(statistics.median(values), 3) if values else 0.0,
        "p95": round(percentile(values, 0.95), 3),
        "max": round(max(values, default=0.0), 3),
    }


def gpu_used_mib() -> int | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            return None
        lines = completed.stdout.strip().splitlines()
        return int(lines[0]) if lines else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def tree_ram_mib(root_pid: int) -> float | None:
    try:
        import psutil

        root = psutil.Process(root_pid)
        processes = [root, *root.children(recursive=True)]
        return sum(process.memory_info().rss for process in processes) / 2**20
    except Exception:  # noqa: BLE001 - a disappearing child is a normal sample race
        return None


class GpuSampler(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self.peak_mib: int | None = None

    def run(self) -> None:
        while not self._stop_event.is_set():
            value = gpu_used_mib()
            if value is not None:
                self.peak_mib = max(self.peak_mib or value, value)
            self._stop_event.wait(0.25)

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=5)


class ProcessTreeGpuSampler(threading.Thread):
    """Measure dedicated GPU memory attributable to one Windows process tree.

    ``nvidia-smi`` reports only a machine-wide total under WDDM, so a browser
    or the desktop compositor can otherwise make a CPU-only BAXY profile look
    as if it allocated CUDA memory. Windows' GPU Process Memory counter retains
    the PID attribution needed for this gate.
    """

    _PID = re.compile(r"^pid_([0-9]+)_", re.IGNORECASE)

    def __init__(self, root_pid: int) -> None:
        super().__init__(daemon=True)
        self._root_pid = root_pid
        self._stop_event = threading.Event()
        self.peak_mib: float | None = None
        self.telemetry_available = False

    @classmethod
    def attributed_bytes(
        cls,
        rows: dict[str, int],
        process_ids: set[int],
    ) -> int:
        total = 0
        for instance, value in rows.items():
            match = cls._PID.match(instance)
            if match is not None and int(match.group(1)) in process_ids:
                total += max(0, int(value))
        return total

    def run(self) -> None:
        query = None
        try:
            import psutil
            import win32pdh

            query = win32pdh.OpenQuery()
            path = win32pdh.MakeCounterPath(
                (
                    None,
                    "GPU Process Memory",
                    "*",
                    None,
                    0,
                    "Dedicated Usage",
                )
            )
            counter = win32pdh.AddCounter(query, path)
            win32pdh.CollectQueryData(query)
            while not self._stop_event.wait(0.25):
                win32pdh.CollectQueryData(query)
                rows = win32pdh.GetFormattedCounterArray(
                    counter,
                    win32pdh.PDH_FMT_LARGE,
                )
                root = psutil.Process(self._root_pid)
                process_ids = {
                    root.pid,
                    *(child.pid for child in root.children(recursive=True)),
                }
                value = self.attributed_bytes(rows, process_ids) / 2**20
                self.telemetry_available = True
                self.peak_mib = max(self.peak_mib or value, value)
        except Exception:
            # Absence of attributable telemetry is itself a failed gate check;
            # disappearing children near shutdown are expected and stop samples.
            return
        finally:
            if query is not None:
                try:
                    import win32pdh

                    win32pdh.CloseQuery(query)
                except Exception:
                    pass

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=5)


class RamSampler(threading.Thread):
    def __init__(self, root_pid: int) -> None:
        super().__init__(daemon=True)
        self._root_pid = root_pid
        self._stop_event = threading.Event()
        self.peak_mib: float | None = None

    def run(self) -> None:
        while not self._stop_event.is_set():
            value = tree_ram_mib(self._root_pid)
            if value is not None:
                self.peak_mib = max(self.peak_mib or value, value)
            self._stop_event.wait(0.25)

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=5)


class JsonLineProcess:
    """Timeout-safe JSONL process client for Windows pipes."""

    def __init__(
        self,
        command: list[str],
        *,
        environment: dict[str, str],
        cwd: Path,
    ) -> None:
        self._messages: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._stderr_tail: list[str] = []
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            cwd=str(cwd),
            bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    @property
    def pid(self) -> int:
        return self._process.pid

    def _read_stdout(self) -> None:
        try:
            assert self._process.stdout is not None
            for line in self._process.stdout:
                if line.strip():
                    self._messages.put(json.loads(line))
            self._messages.put(EOFError("el proceso cerró stdout"))
        except BaseException as error:  # noqa: BLE001
            self._messages.put(error)

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr_tail.append(line.rstrip())
            if len(self._stderr_tail) > 100:
                del self._stderr_tail[:50]

    def next_message(self, timeout: float) -> dict[str, Any]:
        try:
            value = self._messages.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError("el proceso agotó su deadline JSONL") from error
        if isinstance(value, BaseException):
            raise value
        return value

    def request(self, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        if self._process.poll() is not None or self._process.stdin is None:
            raise RuntimeError("el proceso JSONL no está disponible")
        self._process.stdin.write(
            json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self._process.stdin.flush()
        request_id = message.get("id")
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("la solicitud agotó su deadline")
            reply = self.next_message(remaining)
            if reply.get("id") == request_id:
                return reply

    def close(
        self,
        *,
        graceful_message: dict[str, Any] | None,
        timeout: float,
    ) -> None:
        if self._process.poll() is None and self._process.stdin is not None:
            try:
                if graceful_message is not None:
                    self._process.stdin.write(
                        json.dumps(graceful_message, separators=(",", ":")) + "\n"
                    )
                    self._process.stdin.flush()
                else:
                    self._process.stdin.close()
                self._process.wait(timeout=timeout)
            except (OSError, subprocess.TimeoutExpired):
                self._process.kill()
        if self._process.poll() is None:
            self._process.kill()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()


def load_catalog_file(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("capabilities")
    if not isinstance(value, list) or not value:
        raise ValueError("el catálogo debe contener una lista no vacía")
    capabilities = []
    for capability in value:
        if not isinstance(capability, dict):
            raise ValueError("el catálogo contiene una capacidad inválida")
        capabilities.append(
            {
                key: capability[key]
                for key in ("name", "description", "argumentsSchema", "risk")
            }
        )
    return capabilities


def discover_core(
    explicit: Path | None,
    *,
    candidates: Iterable[Path] | None = None,
) -> Path:
    if explicit is not None:
        try:
            core = explicit.resolve(strict=True)
        except (FileNotFoundError, OSError) as error:
            raise FileNotFoundError(
                f"no existe el baxy-core indicado por --core: {explicit}"
            ) from error
        if not core.is_file():
            raise FileNotFoundError(
                f"la ruta indicada por --core no es un archivo: {explicit}"
            )
        return core

    ordered_candidates = tuple(
        DEFAULT_CORE_CANDIDATES if candidates is None else candidates
    )
    core = next(
        (candidate for candidate in ordered_candidates if candidate.is_file()),
        None,
    )
    if core is None:
        checked = "\n".join(f"- {candidate}" for candidate in ordered_candidates)
        raise FileNotFoundError(
            "no se encontró baxy-core para la medición de fuente; "
            "compila Baxy.Core en Release o indica --core."
            + (f"\nRutas Release comprobadas:\n{checked}" if checked else "")
        )
    return core.resolve(strict=True)


def current_core_catalog_snapshot(
    core: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Read the authenticated operation and application catalogues from Core."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError(
            "Windows no publicó LOCALAPPDATA para crear el perfil privado del core"
        )
    private_parent = Path(local_app_data).resolve() / "BAXY"
    data_root = private_parent / f"mind-budget-core-{uuid.uuid4().hex}"
    try:
        # The canonical Release apphost is framework-dependent. Resolve the
        # repository's pinned SDK/runtime exactly as the development launcher
        # does; inheriting the machine-wide dotnet root can otherwise launch it
        # against an older runtime and make the physical gate fail before hello.
        environment = environment_for_dotnet(dotnet_executable())
        environment["BAXY_DATA_DIR"] = str(data_root)
        client = JsonLineProcess(
            [str(core)],
            environment=environment,
            cwd=REPO,
        )
        try:
            hello = client.next_message(30.0)
            capabilities = hello.get("capabilities")
            if hello.get("type") != "hello" or not isinstance(capabilities, list):
                raise RuntimeError("el core no publicó un catálogo autenticado")
            application_catalog = hello.get("applicationCatalog")
            if application_catalog is not None and not isinstance(
                application_catalog,
                dict,
            ):
                raise RuntimeError(
                    "el core publicó un catálogo de aplicaciones inválido"
                )
            game_catalog = hello.get("gameCatalog")
            if game_catalog is not None and not isinstance(game_catalog, dict):
                raise RuntimeError("el core publicó un catálogo de juegos inválido")
            return [
                {
                    key: capability[key]
                    for key in ("name", "description", "argumentsSchema", "risk")
                }
                for capability in capabilities
            ], application_catalog, game_catalog
        finally:
            client.close(graceful_message=None, timeout=15.0)
    finally:
        # BAXY only accepts a direct child of its trusted private parent. Keep
        # that invariant explicit before cleaning the gate-owned profile.
        if (
            data_root.parent == private_parent
            and data_root.name.startswith("mind-budget-core-")
        ):
            shutil.rmtree(data_root, ignore_errors=True)


def current_core_capabilities(core: Path) -> list[dict[str, Any]]:
    capabilities, _, _ = current_core_catalog_snapshot(core)
    return capabilities


def sidecar_environment(
    runtime: RuntimeConfig,
    *,
    gpu_layers: int,
    llm_http_timeout: float,
    router_start_stress: bool = False,
) -> dict[str, str]:
    environment = os.environ.copy()
    existing_python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(runtime.python_path) + (
        os.pathsep + existing_python_path if existing_python_path else ""
    )
    environment["PYTHONUTF8"] = "1"
    environment["HF_HUB_OFFLINE"] = "1"
    environment["BAXY_MIND_LLM_GGUF"] = str(runtime.gguf)
    environment["BAXY_MIND_LLAMA_SERVER"] = str(runtime.llama_server)
    environment["BAXY_MIND_NGL"] = str(gpu_layers)
    environment["BAXY_MIND_CTX"] = "4096"
    environment["BAXY_MIND_LLM_REQUEST_TIMEOUT"] = str(llm_http_timeout)
    # La certificación principal ejerce el default productivo del retraso del
    # worker E5 (3 s desde 2026-07-30). El escenario de estrés con arranque
    # inmediato del encoder es explícito y separado; ya no se fuerza en
    # silencio un interleaving distinto del producto.
    if router_start_stress:
        environment["BAXY_MIND_ROUTER_START_DELAY"] = "0"
    else:
        environment.pop("BAXY_MIND_ROUTER_START_DELAY", None)
    # El gate mide el servidor registrado, no un endpoint heredado e invisible.
    environment.pop("BAXY_MIND_LLM_ENDPOINT", None)
    return environment


def validate_reply(item: WorkItem, reply: dict[str, Any]) -> str:
    """Return a stable failure code; never return model text or error details."""

    reply_type = reply.get("type")
    if reply_type == "error":
        code = str(reply.get("code") or "unknown")
        return "sidecar_error:" + (
            code if code.replace("_", "").isalnum() else "unknown"
        )
    if reply_type != item.expected_reply_type:
        return "unexpected_reply_type"
    if item.request_type == "turn.decide":
        kind = reply.get("kind")
        if kind not in {"conversation", "clarify", "action", "plan"}:
            return "invalid_turn_kind"
        if kind == "conversation" and not str(reply.get("reply") or "").strip():
            return "empty_conversation_reply"
        if kind == "clarify" and not str(reply.get("question") or "").strip():
            return "empty_clarification"
        if kind == "action" and not str(reply.get("operation") or "").strip():
            return "missing_action_operation"
    elif item.request_type == "arguments":
        if reply.get("operation") != item.message.get("operation"):
            return "unexpected_argument_operation"
        if reply.get("ok") is True:
            if not isinstance(reply.get("arguments"), dict):
                return "invalid_grounded_arguments"
        elif not (
            reply.get("ok") is False
            and reply.get("arguments") is None
            and str(reply.get("question") or "").strip()
        ):
            return "invalid_safe_clarification"
    elif item.request_type == "narrate" and not str(reply.get("text") or "").strip():
        return "empty_narration"
    return ""


def _reply_operations(reply: dict[str, Any], field: str) -> tuple[str, ...]:
    value = reply.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return ()
    return tuple(value)


def validate_semantic_reply(item: WorkItem, reply: dict[str, Any]) -> str:
    """Validate the frozen workload meaning without inspecting generated prose."""

    if item.request_type == "turn.decide":
        index = int(item.case_id.rsplit("-", 1)[1])
        expectation, expected_operation = TURN_EXPECTATIONS[index]
        kind = reply.get("kind")
        operation = reply.get("operation")
        intents = _reply_operations(reply, "intentOperations")
        effects = _reply_operations(reply, "effectOperations")

        if expectation == "app_owned_no_effect":
            if effects or operation is not None or kind not in {"conversation", "clarify"}:
                return "semantic_unexpected_effect"
            return ""
        if expectation == "conversation":
            return "" if kind == "conversation" and not effects else "semantic_turn_kind"
        if expectation == "conversation_or_action" and kind == "conversation":
            return "" if not effects else "semantic_unexpected_effect"
        if expectation == "clarify":
            if kind != "clarify" or effects or operation is not None:
                return "semantic_turn_kind"
            return (
                ""
                if intents == (expected_operation,)
                else "semantic_intent_operation"
            )
        if expectation in {"action", "conversation_or_action"}:
            if kind != "action":
                return "semantic_turn_kind"
            if operation != expected_operation:
                return "semantic_action_operation"
            if intents != (expected_operation,) or effects != (expected_operation,):
                return "semantic_effect_operation"
            return ""
        return "semantic_oracle_invalid"

    if item.request_type == "arguments":
        index = int(item.case_id.rsplit("-", 1)[1])
        if reply.get("ok") is not True or not isinstance(reply.get("arguments"), dict):
            return "semantic_arguments_missing"
        if reply["arguments"] not in ARGUMENT_EXPECTATIONS[index]:
            return "semantic_arguments_mismatch"
    return ""


def reply_signature(item: WorkItem, reply: dict[str, Any]) -> dict[str, Any]:
    """Project one response without publishing generated user-visible text."""

    canonical = {key: value for key, value in reply.items() if key != "id"}
    canonical_bytes = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if item.request_type == "turn.decide":
        contract = {
            "type": reply.get("type"),
            "kind": reply.get("kind"),
            "operation": reply.get("operation"),
            "intent_operations": list(reply.get("intentOperations") or []),
            "effect_operations": list(reply.get("effectOperations") or []),
            "question_nonempty": bool(str(reply.get("question") or "").strip()),
            "reply_nonempty": bool(str(reply.get("reply") or "").strip()),
            "turn_recovery": reply.get("turn_recovery"),
            "failure_code": reply.get("failure_code"),
        }
    elif item.request_type == "arguments":
        contract = {
            "type": reply.get("type"),
            "operation": reply.get("operation"),
            "ok": reply.get("ok"),
            "arguments": reply.get("arguments"),
            "question_nonempty": bool(str(reply.get("question") or "").strip()),
            "code": reply.get("code"),
        }
    else:
        contract = {
            "type": reply.get("type"),
            "text_nonempty": bool(str(reply.get("text") or "").strip()),
            "code": reply.get("code"),
        }
    contract_bytes = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "case_id": item.case_id,
        "request_type": item.request_type,
        "contract_projection": contract,
        "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
        "complete_reply_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
    }


def stable_exception_code(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, (BrokenPipeError, EOFError, ConnectionError)):
        return "process_unavailable"
    if isinstance(error, json.JSONDecodeError):
        return "invalid_json"
    return "runtime_exception"


def run_profile(
    name: str,
    runtime: RuntimeConfig,
    capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    limits = PROFILE_LIMITS[name]
    layers = runtime.gpu_layers if name == "gpu" else 0
    baseline_vram = gpu_used_mib()
    gpu_sampler = GpuSampler()
    gpu_sampler.start()
    start = time.perf_counter()
    handshake_deadline = start + limits["handshake"]
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=sidecar_environment(
            runtime,
            gpu_layers=layers,
            llm_http_timeout=limits["llm_http"],
        ),
        cwd=REPO,
    )
    ram_sampler = RamSampler(client.pid)
    ram_sampler.start()
    process_gpu_sampler = ProcessTreeGpuSampler(client.pid)
    process_gpu_sampler.start()
    errors: list[dict[str, str]] = []
    latencies: dict[str, list[float]] = {
        "turn.decide": [],
        "arguments": [],
        "narrate": [],
    }
    completed = 0
    response_signatures: list[dict[str, Any]] = []
    hello_seconds = 0.0
    ready_seconds = 0.0
    aborted = False
    try:
        hello = client.next_message(
            max(0.0, handshake_deadline - time.perf_counter())
        )
        hello_seconds = time.perf_counter() - start
        if hello.get("type") != "hello" or "llm" not in (hello.get("models") or {}):
            raise RuntimeError("hello sin LLM")
        catalog_reply = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-{name}",
                "capabilities": capabilities,
            },
            max(0.0, handshake_deadline - time.perf_counter()),
        )
        ready_seconds = time.perf_counter() - start
        if (
            catalog_reply.get("type") != "catalog.ready"
            or catalog_reply.get("count") != len(capabilities)
        ):
            raise RuntimeError("catálogo rechazado")

        for item in build_workload():
            begin = time.perf_counter()
            try:
                reply = client.request(item.message, limits[item.request_type])
                latency = time.perf_counter() - begin
                latencies[item.request_type].append(latency)
                completed += 1
                response_signatures.append(reply_signature(item, reply))
                failure = validate_reply(item, reply) or validate_semantic_reply(
                    item,
                    reply,
                )
                if failure:
                    errors.append(
                        {
                            "case_id": item.case_id,
                            "request_type": item.request_type,
                            "reason": failure,
                        }
                    )
            except BaseException as error:  # noqa: BLE001 - gate records and aborts
                latencies[item.request_type].append(time.perf_counter() - begin)
                errors.append(
                    {
                        "case_id": item.case_id,
                        "request_type": item.request_type,
                        "reason": stable_exception_code(error),
                    }
                )
                aborted = True
                break
    except BaseException as error:  # noqa: BLE001 - stable report, no local detail
        errors.append(
            {
                "case_id": "profile-startup",
                "request_type": "startup",
                "reason": stable_exception_code(error),
            }
        )
        aborted = True
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"shutdown-{name}"},
            timeout=limits["shutdown"],
        )
        ram_sampler.stop()
        gpu_sampler.stop()
        process_gpu_sampler.stop()

    peak_vram = gpu_sampler.peak_mib
    process_peak_vram = process_gpu_sampler.peak_mib
    vram_delta = (
        max(0, peak_vram - baseline_vram)
        if peak_vram is not None and baseline_vram is not None
        else None
    )
    return {
        "gpu_layers": layers,
        "timeouts_seconds": {
            key: value
            for key, value in limits.items()
            if key not in {"shutdown"}
        },
        "startup": {
            "hello_seconds": round(hello_seconds, 3),
            "catalog_ready_seconds": round(ready_seconds, 3),
        },
        "gpu_telemetry_available": (
            baseline_vram is not None and peak_vram is not None
        ),
        "vram_baseline_total_mib": baseline_vram,
        "vram_peak_total_mib": peak_vram,
        "vram_delta_mib": vram_delta,
        "process_gpu_telemetry_available": (
            process_gpu_sampler.telemetry_available
            and process_peak_vram is not None
        ),
        "process_tree_vram_peak_mib": (
            round(process_peak_vram, 1)
            if process_peak_vram is not None
            else None
        ),
        "tree_ram_peak_mib": (
            round(ram_sampler.peak_mib, 1)
            if ram_sampler.peak_mib is not None
            else None
        ),
        "requests_expected": EXPECTED_REQUESTS,
        "requests_completed": completed,
        "requests_skipped_after_abort": EXPECTED_REQUESTS - completed,
        "aborted": aborted,
        "errors": errors,
        "response_signatures": response_signatures,
        "latency_seconds": {
            kind: latency_summary(values) for kind, values in latencies.items()
        },
    }


def evaluate_profile(
    name: str,
    profile: dict[str, Any],
    *,
    gpu_vram_budget_mib: int,
    cpu_vram_tolerance_mib: int,
    cpu_ram_budget_mib: int,
    cpu_turn_p50_budget_seconds: float,
) -> dict[str, Any]:
    common = {
        "all_requests_completed": (
            profile["requests_completed"] == profile["requests_expected"]
        ),
        "zero_errors": not profile["errors"],
        "gpu_telemetry_available": profile["gpu_telemetry_available"],
        "process_gpu_telemetry_available": profile[
            "process_gpu_telemetry_available"
        ],
        "startup_within_shell_handshake": (
            profile["startup"]["catalog_ready_seconds"] > 0
            and profile["startup"]["catalog_ready_seconds"]
            <= profile["timeouts_seconds"]["handshake"]
        ),
    }
    attributed = profile.get("process_tree_vram_peak_mib")
    if name == "gpu":
        checks = {
            **common,
            "vram_within_budget": (
                isinstance(attributed, (int, float))
                and attributed <= gpu_vram_budget_mib
            ),
        }
    else:
        turn_p50 = profile["latency_seconds"]["turn.decide"]["p50"]
        tree_ram_peak_mib = profile.get("tree_ram_peak_mib")
        checks = {
            **common,
            "no_material_gpu_allocation": (
                isinstance(attributed, (int, float))
                and attributed <= cpu_vram_tolerance_mib
            ),
            "ram_within_budget": (
                isinstance(tree_ram_peak_mib, (int, float))
                and tree_ram_peak_mib <= cpu_ram_budget_mib
            ),
            "turn_p50_within_transport_sla": (
                profile["latency_seconds"]["turn.decide"]["count"] > 0
                and turn_p50 <= cpu_turn_p50_budget_seconds
            ),
        }
    status = "passed" if all(checks.values()) else "failed"
    return {**profile, "checks": checks, "status": status}


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate físico de VRAM, RAM, fallback CPU y latencia de baxy-mind."
    )
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--catalog-file", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--gpu-vram-budget-mib",
        type=int,
        default=GPU_VRAM_BUDGET_MIB,
    )
    parser.add_argument(
        "--cpu-vram-tolerance-mib",
        type=int,
        default=CPU_VRAM_TOLERANCE_MIB,
    )
    parser.add_argument(
        "--cpu-ram-budget-mib",
        type=int,
        default=CPU_RAM_BUDGET_MIB,
    )
    parser.add_argument(
        "--cpu-turn-p50-budget-seconds",
        type=float,
        default=CPU_TURN_P50_BUDGET_SECONDS,
    )
    args = parser.parse_args()
    if args.gpu_vram_budget_mib < 1:
        parser.error("--gpu-vram-budget-mib debe ser positivo")
    if args.cpu_vram_tolerance_mib < 0:
        parser.error("--cpu-vram-tolerance-mib no puede ser negativo")
    if args.cpu_ram_budget_mib < 1:
        parser.error("--cpu-ram-budget-mib debe ser positivo")
    if args.cpu_turn_p50_budget_seconds <= 0:
        parser.error("--cpu-turn-p50-budget-seconds debe ser positivo")
    return args


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    runtime = resolve_runtime_from_args(args)
    capabilities = (
        load_catalog_file(args.catalog_file)
        if args.catalog_file is not None
        else current_core_capabilities(discover_core(args.core))
    )
    profiles = {
        "gpu": evaluate_profile(
            "gpu",
            run_profile("gpu", runtime, capabilities),
            gpu_vram_budget_mib=args.gpu_vram_budget_mib,
            cpu_vram_tolerance_mib=args.cpu_vram_tolerance_mib,
            cpu_ram_budget_mib=args.cpu_ram_budget_mib,
            cpu_turn_p50_budget_seconds=args.cpu_turn_p50_budget_seconds,
        ),
        "cpu_fallback": evaluate_profile(
            "cpu_fallback",
            run_profile("cpu_fallback", runtime, capabilities),
            gpu_vram_budget_mib=args.gpu_vram_budget_mib,
            cpu_vram_tolerance_mib=args.cpu_vram_tolerance_mib,
            cpu_ram_budget_mib=args.cpu_ram_budget_mib,
            cpu_turn_p50_budget_seconds=args.cpu_turn_p50_budget_seconds,
        ),
    }
    report = {
        "schema": "baxy-mind-budget-gate-v6",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "adr": "ADR-0005",
        "status": (
            "passed"
            if all(profile["status"] == "passed" for profile in profiles.values())
            else "failed"
        ),
        "method": {
            "gpu_memory": (
                "pico de memoria GPU dedicada atribuido al árbol de procesos "
                "mediante GPU Process Memory; nvidia-smi total queda como contexto"
            ),
            "ram": "pico RSS del árbol sidecar + llama-server",
            "startup": (
                "saludo y catalogo comparten el deadline acumulado de "
                "120 segundos del shell"
            ),
            "effects_executed": 0,
            "private_paths_in_report": False,
        },
        "limits": {
            "gpu_vram_budget_mib": args.gpu_vram_budget_mib,
            "cpu_vram_tolerance_mib": args.cpu_vram_tolerance_mib,
            "cpu_ram_budget_mib": args.cpu_ram_budget_mib,
            "cpu_turn_p50_budget_seconds": args.cpu_turn_p50_budget_seconds,
        },
        "runtime": public_runtime_identity(runtime),
        "catalog_operations": len(capabilities),
        "workload": {
            "turn.decide": len(TURN_TEXTS),
            "arguments": len(ARGUMENT_CASES),
            "narrate": len(NARRATE_CASES),
            "total_per_profile": EXPECTED_REQUESTS,
            "semantic_oracle": "frozen-contract-v2",
            "ownership": (
                "turnos de memoria se validan en la compuerta App y no se "
                "envían al sidecar Mind"
            ),
        },
        "profiles": profiles,
    }
    write_json_atomic(args.output.resolve(), report)
    return report


def main() -> int:
    report = run_gate(parse_args())
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "status": report["status"],
                "profiles": {
                    name: {
                        "status": profile["status"],
                        "requests_completed": profile["requests_completed"],
                        "errors": len(profile["errors"]),
                    }
                    for name, profile in report["profiles"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
