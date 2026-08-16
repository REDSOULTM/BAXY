"""Encoder multilingüe compartido y router semántico offline (ADR-0005).

El proceso usado por el runtime de producto expone únicamente embeddings. La
política contextual del LLM y sus contratos cerrados son quienes deciden
conversation/action/plan; el worker no dispone de una llamada de ruteo.

``IntentRouter`` conserva la evaluación semántica del banco congelado para
gates offline y compatibilidad de pruebas. Sus decisiones nacen sólo de los
pools de embeddings y nunca reciben autoridad en el protocolo de producción.

Banco congelado en data/intent_bank.jsonl (anclas autoradas + corpus curado,
generado por tools/build_bank.py). Umbrales congelados en el torneo:
tau=0.90, margen=0.005 (tournament_encoder_protocol.json, e5-small).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .process_lifecycle import (
    MAX_PROCESS_REAP_TIMEOUT_SECONDS,
    ReapResource,
    report_incomplete_reap,
    terminate_and_reap_bounded,
)
from .time_budget import remaining_seconds

MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MODEL_SNAPSHOT_MANIFEST_SHA256 = (
    "e1ab2f71784b5129f89096ef377e9f573fa06d0f11c64f897560486524fd4940"
)
MODEL_SNAPSHOT_FILE_COUNT = 10
MODEL_WEIGHTS_SHA256 = (
    "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477"
)
MODEL_SNAPSHOT_MANIFEST_ALGORITHM = (
    "sha256(UTF-8/LF/final-LF lines: model, revision, then every file sorted "
    "by relative POSIX path UTF-8 bytes as path<TAB>size<TAB>sha256)"
)
QUERY_PREFIX = "query: "
FROZEN_TAU = 0.90
FROZEN_MARGIN = 0.005
BANK_PATH = Path(__file__).resolve().parent / "data" / "intent_bank.jsonl"
POOL_PATH = Path(__file__).resolve().parent / "data" / "intent_bank.embeddings.npy"
POOL_METADATA_PATH = Path(__file__).resolve().parent / "data" / "intent_bank.embeddings.json"
DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_INTERACTIVE_ENCODER_TIMEOUT_SECONDS = 0.75
ROUTER_CLOSE_TOTAL_TIMEOUT_SECONDS = 0.75
ROUTER_CLOSE_GRACEFUL_LOCK_TIMEOUT_SECONDS = 0.05
ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS = 0.25
MAX_ENCODER_BATCH_SIZE = 4_096
MAX_ENCODER_TEXT_CHARS = 4_096


@dataclass(frozen=True, slots=True)
class EncoderSnapshotIdentity:
    model: str
    revision: str
    manifest_sha256: str
    file_count: int
    weights_sha256: str

    def public_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "revision": self.revision,
            "manifest_algorithm": MODEL_SNAPSHOT_MANIFEST_ALGORITHM,
            "manifest_sha256": self.manifest_sha256,
            "file_count": self.file_count,
            "weights": {
                "path": "model.safetensors",
                "sha256": self.weights_sha256,
            },
        }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _encoder_snapshot_identity(
    snapshot: Path,
    *,
    model: str = MODEL_NAME,
    revision: str = MODEL_REVISION,
) -> EncoderSnapshotIdentity:
    """Hash the exact snapshot with a portable, deterministic manifest.

    The UTF-8/LF manifest has model and immutable revision headers followed by
    every regular file, sorted ordinally by the UTF-8 bytes of its relative
    POSIX path. Each file row contains path, byte size and content SHA-256
    separated by tabs, with one final LF.
    """

    snapshot = snapshot.resolve(strict=True)
    if not snapshot.is_dir():
        raise ValueError("el snapshot E5 no es un directorio")
    entries: list[tuple[str, int, str]] = []
    for path in snapshot.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(snapshot).as_posix()
        entries.append((relative, path.stat().st_size, _file_sha256(path)))
    entries.sort(key=lambda item: item[0].encode("utf-8"))
    lines = [f"model={model}", f"revision={revision}"]
    lines.extend(
        f"{relative}\t{size}\t{digest}"
        for relative, size, digest in entries
    )
    manifest_sha256 = hashlib.sha256(
        (("\n".join(lines)) + "\n").encode("utf-8")
    ).hexdigest()
    weights_sha256 = next(
        (
            digest
            for relative, _, digest in entries
            if relative == "model.safetensors"
        ),
        "",
    )
    return EncoderSnapshotIdentity(
        model=model,
        revision=revision,
        manifest_sha256=manifest_sha256,
        file_count=len(entries),
        weights_sha256=weights_sha256,
    )


@lru_cache(maxsize=1)
def _verified_encoder_snapshot() -> tuple[Path, EncoderSnapshotIdentity]:
    """Resolve and attest the immutable local E5 snapshot, or fail closed."""

    from huggingface_hub import snapshot_download

    try:
        snapshot = Path(
            snapshot_download(
                repo_id=MODEL_NAME,
                revision=MODEL_REVISION,
                local_files_only=True,
            )
        ).resolve(strict=True)
        identity = _encoder_snapshot_identity(snapshot)
    except Exception as error:
        raise RuntimeError(
            "no se pudo resolver y verificar el snapshot E5 fijado"
        ) from error
    if (
        identity.manifest_sha256 != MODEL_SNAPSHOT_MANIFEST_SHA256
        or identity.file_count != MODEL_SNAPSHOT_FILE_COUNT
        or identity.weights_sha256 != MODEL_WEIGHTS_SHA256
    ):
        raise RuntimeError(
            "el snapshot E5 local no coincide con la identidad física fijada"
        )
    return snapshot, identity


def verified_encoder_snapshot_identity() -> dict[str, object]:
    """Return the release-safe identity after verifying every snapshot file."""

    _, identity = _verified_encoder_snapshot()
    return identity.public_dict()

# Etiquetas del banco offline → operación del catálogo congelado. Las etiquetas
# de scope llevan argumentos completos; el resto requiere extracción posterior.
_COMPLETE_ARG_SCOPES = {
    "cpu", "memory", "disk", "battery", "os", "summary",
    "cpu_memory", "os_memory", "gpu_identity", "gpu_usage",
}

_COMPLETE_ARGUMENT_OPERATIONS = {
    "system.time": {},
}


@dataclass(frozen=True)
class RouteDecision:
    kind: str  # "operation" | "conversation"
    operation: str | None = None
    arguments: dict | None = None
    needs_arguments: bool = False
    confidence: float = 0.0
    winner_pool: str = ""


def _load_frozen_pool(
    bank_path: Path,
    pool_path: Path,
    metadata_path: Path,
    *,
    expected_rows: int,
):
    """Load the versioned router vectors only when they match the bank exactly."""

    import numpy as np

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        bank_digest = hashlib.sha256(bank_path.read_bytes()).hexdigest()
        if (
            metadata.get("schema") != "baxy-intent-pool-v1"
            or metadata.get("model") != MODEL_NAME
            or metadata.get("bank_sha256") != bank_digest
            or metadata.get("rows") != expected_rows
            or metadata.get("pool_sha256")
            != hashlib.sha256(pool_path.read_bytes()).hexdigest()
        ):
            return None
        pool = np.load(pool_path, allow_pickle=False)
        if (
            pool.dtype != np.float32
            or pool.ndim != 2
            or pool.shape[0] != expected_rows
            or pool.shape[1] < 1
            or metadata.get("dimensions") != pool.shape[1]
            or not np.isfinite(pool).all()
        ):
            return None
        return pool
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


class SemanticEncoder:
    """Pinned E5 encoder used by the production worker.

    This class intentionally has no ``route`` method. Keeping the product
    subprocess encoder-only makes it impossible for an old phrase gate or an
    offline intent-bank label to become execution authority accidentally.
    """

    def __init__(self, device: str = "cpu") -> None:
        from sentence_transformers import SentenceTransformer

        verified_encoder_snapshot_identity()
        self._model = SentenceTransformer(
            MODEL_NAME,
            device=device,
            revision=MODEL_REVISION,
            local_files_only=True,
        )

    def encode(self, texts: list[str] | tuple[str, ...]):
        return self._model.encode(
            [QUERY_PREFIX + text for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
        )


class IntentRouter(SemanticEncoder):
    """Offline nearest-pool evaluator; never instantiated by the product worker."""

    def __init__(
        self,
        bank_path: Path = BANK_PATH,
        device: str = "cpu",
        pool_path: Path = POOL_PATH,
        pool_metadata_path: Path = POOL_METADATA_PATH,
    ) -> None:
        super().__init__(device=device)
        self._class_names: list[str] = []
        class_index: dict[str, int] = {}
        self._class_of_row: list[int] = []
        sentences: list[str] = []
        with open(bank_path, encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                label, text = row["label"], row["text"]
                if label not in class_index:
                    class_index[label] = len(self._class_names)
                    self._class_names.append(label)
                sentences.append(QUERY_PREFIX + text)
                self._class_of_row.append(class_index[label])
        if not sentences:
            raise ValueError("banco de intención vacío")
        self._pool = _load_frozen_pool(
            bank_path,
            pool_path,
            pool_metadata_path,
            expected_rows=len(sentences),
        )
        if self._pool is None:
            self._pool = self._model.encode(
                sentences, normalize_embeddings=True, show_progress_bar=False
            )
        rows_by_class: dict[int, list[int]] = defaultdict(list)
        for row, cls in enumerate(self._class_of_row):
            rows_by_class[cls].append(row)
        self._rows_by_class = rows_by_class

    def route(self, text: str) -> RouteDecision:
        return self.route_many((text,), batch_size=1)[0]

    def route_many(
        self,
        texts: list[str] | tuple[str, ...],
        *,
        batch_size: int = 256,
    ) -> list[RouteDecision]:
        """Route a frozen corpus efficiently without changing decisions.

        Historical acceptance gates contain thousands of exact messages.  A
        single encoder call per message made exhaustive verification
        needlessly slow; bounded matrix batches produce the same pool maxima
        while keeping memory stable.
        """

        import numpy as np

        if not texts:
            return []
        if batch_size < 1:
            raise ValueError("batch_size must be positive")

        decisions: list[RouteDecision] = []
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            queries = self._model.encode(
                [QUERY_PREFIX + text for text in batch],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            similarities = queries @ self._pool.T
            for _, sims in zip(batch, similarities, strict=True):
                scores = np.array(
                    [
                        sims[self._rows_by_class[cls]].max()
                        for cls in range(len(self._class_names))
                    ]
                )
                order = np.argsort(-scores)
                best_index = int(order[0])
                best = float(scores[best_index])
                second = float(scores[int(order[1])])
                winner = self._class_names[best_index]

                if (
                    winner.startswith("ABSTAIN__")
                    or best < FROZEN_TAU
                    or (best - second) < FROZEN_MARGIN
                ):
                    decisions.append(
                        RouteDecision(
                            kind="conversation",
                            confidence=best,
                            winner_pool=winner,
                        )
                    )
                else:
                    decisions.append(self._decision_for(winner, best))
        return decisions

    def _decision_for(self, label: str, confidence: float) -> RouteDecision:
        if label in _COMPLETE_ARGUMENT_OPERATIONS:
            return RouteDecision(
                kind="operation",
                operation=label,
                arguments=dict(_COMPLETE_ARGUMENT_OPERATIONS[label]),
                confidence=confidence,
                winner_pool=label,
            )
        if label.startswith("system.status:"):
            scope = label.split(":", 1)[1]
            if scope in _COMPLETE_ARG_SCOPES:
                return RouteDecision(
                    kind="operation",
                    operation="system.status",
                    arguments={"scope": scope},
                    confidence=confidence,
                    winner_pool=label,
                )
        if label == "audio.status":
            return RouteDecision(
                kind="operation",
                operation="audio.status",
                arguments={},
                confidence=confidence,
                winner_pool=label,
            )
        # Operaciones con argumentos por extraer (note.create, audio.volume,
        # audio.mute, memory.*): el shell decide la capa de argumentos
        # (parser determinista o LLM con tool forzada).
        return RouteDecision(
            kind="operation",
            operation=label,
            arguments=None,
            needs_arguments=True,
            confidence=confidence,
            winner_pool=label,
        )


class ProcessIntentRouter:
    """Run the heavyweight encoder outside the protocol process.

    SentenceTransformer/OpenMP initialization can stall when performed in a
    background thread. A single encoder-only worker preserves serialized model
    access while making semantic routing unavailable at this boundary.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._responses: queue.Queue[dict] = queue.Queue()
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._is_ready = False
        self._failed = False
        self._failure = ""
        self._next_request_id = 1
        self._closed = threading.Event()
        self._launcher = threading.Thread(
            target=self._launch_and_read,
            name="baxy-router-launcher",
            daemon=True,
        )
        self._launcher.start()

    def _launch_and_read(self) -> None:
        # 3 s keeps the worker spawn clear of the llama warmup burst that
        # motivated the original 6 s guard, while shortening the degraded
        # lexical window ~2-4 s. Paired A/B in both orders kept the first
        # turn at or below the 6 s baseline (router_delay_{6,0,3}_{a,b}
        # artifacts, 2026-07-30); 0 s showed an unstable first-turn cost.
        try:
            delay = float(os.environ.get("BAXY_MIND_ROUTER_START_DELAY", "3"))
        except ValueError:
            delay = 3.0
        if self._closed.wait(timeout=max(0.0, min(15.0, delay))):
            return
        creation_flags = 0x08000000 if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-m", "baxy_mind.router_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=creation_flags,
            )
        except OSError:
            self._responses.put({"type": "closed"})
            return
        with self._lifecycle_lock:
            # ``request_close`` sets the event before entering this small
            # publication section. A child created during shutdown is killed
            # locally and never becomes the router's active process.
            if self._closed.is_set():
                status = terminate_and_reap_bounded(
                    process,
                    timeout=ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS,
                    final_wait=(
                        ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS / 2.0
                    ),
                )
                report_incomplete_reap(
                    ReapResource.ROUTER_PROCESS,
                    status,
                )
                self._responses.put({"type": "closed"})
                return
            self._process = process
        self._read_responses()

    def _read_responses(self) -> None:
        process = self._process
        stream = process.stdout if process is not None else None
        if stream is None:
            self._responses.put({"type": "closed"})
            return
        try:
            for line in stream:
                try:
                    response = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    self._responses.put({"type": "protocol.error"})
                    return
                if not isinstance(response, dict):
                    self._responses.put({"type": "protocol.error"})
                    return
                self._responses.put(response)
        except OSError:
            pass
        finally:
            self._responses.put({"type": "closed"})

    def _receive(self, timeout: float | None = None) -> dict:
        try:
            response = self._responses.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError("router worker response timed out") from error
        if response.get("type") == "closed":
            raise RuntimeError("router worker closed unexpectedly")
        return response

    def _wait_ready(self, timeout: float | None = None) -> None:
        with self._lifecycle_lock_for():
            if self._closed.is_set():
                raise RuntimeError("router worker is closed")
            if self._is_ready:
                return
        response = self._receive(timeout)
        if response != {"type": "ready"}:
            raise RuntimeError("router worker did not initialize")
        with self._lifecycle_lock_for():
            if self._closed.is_set():
                raise RuntimeError("router worker closed during readiness")
            self._is_ready = True

    def try_ready(self, timeout: float = 0.0) -> bool:
        """Observe readiness without turning normal cold start into a failure."""

        try:
            timeout = float(timeout)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(timeout):
            return False
        timeout = max(0.0, timeout)
        deadline = time.monotonic() + timeout
        if not self._lock.acquire(timeout=timeout):
            return False
        try:
            if self._failed or self._closed.is_set():
                return False
            try:
                self._wait_ready(
                    remaining_seconds(
                        deadline,
                        timeout,
                        now=time.monotonic(),
                    )
                )
            except TimeoutError:
                return False
            except Exception as error:  # noqa: BLE001 - terminal protocol fault
                self._fail_closed_locked(type(error).__name__)
                return False
            return True
        finally:
            self._lock.release()

    def _send(self, request: dict) -> None:
        process = self._process
        stream = process.stdin if process is not None else None
        if process is None or stream is None or process.poll() is not None:
            raise RuntimeError("router worker is not available")
        stream.write(json.dumps(request, ensure_ascii=False) + "\n")
        stream.flush()

    def route(self, text: str, timeout: float | None = None) -> RouteDecision:
        del text, timeout
        raise RuntimeError(
            "el worker de producción es encoder-only; turn.decide posee la política"
        )

    @staticmethod
    def _validated_timeout(timeout: float) -> float:
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or float(timeout) <= 0.0
        ):
            raise ValueError("encoder timeout must be finite and positive")
        return float(timeout)

    @staticmethod
    def _validated_texts(
        texts: list[str] | tuple[str, ...],
    ) -> tuple[str, ...]:
        if (
            not isinstance(texts, (list, tuple))
            or not 1 <= len(texts) <= MAX_ENCODER_BATCH_SIZE
            or any(
                not isinstance(text, str)
                or not text
                or len(text) > MAX_ENCODER_TEXT_CHARS
                for text in texts
            )
        ):
            raise ValueError("encoder batch is invalid")
        return tuple(texts)

    @staticmethod
    def _remaining(deadline: float, maximum: float) -> float:
        remaining = remaining_seconds(
            deadline,
            maximum,
            now=time.monotonic(),
        )
        if remaining <= 0.0:
            raise TimeoutError("router worker request timed out")
        return remaining

    def _allocate_request_id_locked(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _fail_closed_locked(self, reason: str) -> None:
        """Permanently retire a channel after synchronization is uncertain."""

        if self._failed:
            return
        self._failed = True
        self._failure = reason[:128]
        _, process = self._mark_closed_and_snapshot()
        status = terminate_and_reap_bounded(
            process,
            timeout=ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS,
            final_wait=ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS / 2.0,
        )
        report_incomplete_reap(
            ReapResource.ROUTER_PROCESS,
            status,
        )

    def _ensure_usable_locked(self) -> None:
        if self._failed:
            raise RuntimeError("router worker is permanently unavailable")
        if self._closed.is_set():
            raise RuntimeError("router worker is closed")

    def encode(
        self,
        texts: list[str] | tuple[str, ...],
        timeout: float = DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS,
    ):
        import numpy as np

        batch = self._validated_texts(texts)
        timeout = self._validated_timeout(timeout)
        deadline = time.monotonic() + timeout
        if not self._lock.acquire(timeout=timeout):
            raise TimeoutError("router worker is busy")
        try:
            self._ensure_usable_locked()
            try:
                self._wait_ready(self._remaining(deadline, timeout))
                request_id = self._allocate_request_id_locked()
                self._send(
                    {
                        "type": "encode",
                        "id": request_id,
                        "texts": list(batch),
                    }
                )
                response = self._receive(self._remaining(deadline, timeout))
                if (
                    set(response) != {"type", "id", "rows"}
                    or response.get("type") != "encode.result"
                    or response.get("id") != request_id
                    or isinstance(response.get("id"), bool)
                ):
                    raise RuntimeError(
                        "router worker returned a mismatched response"
                    )
                matrix = np.asarray(response["rows"], dtype=np.float32)
                if (
                    matrix.ndim != 2
                    or matrix.shape[0] != len(batch)
                    or not 1 <= matrix.shape[1] <= 4_096
                    or not np.isfinite(matrix).all()
                ):
                    raise RuntimeError(
                        "router worker returned invalid embeddings"
                    )
                return matrix
            except TimeoutError:
                self._fail_closed_locked("timeout")
                raise
            except Exception as error:  # noqa: BLE001 - terminal protocol fault
                self._fail_closed_locked(type(error).__name__)
                if isinstance(error, RuntimeError):
                    raise
                raise RuntimeError("router worker protocol failed") from error
        finally:
            self._lock.release()

    def try_encode(
        self,
        texts: list[str] | tuple[str, ...],
        timeout: float,
    ):
        """Return embeddings or ``None``; no transport failure grants authority."""

        try:
            return self.encode(texts, timeout=timeout)
        except Exception:  # noqa: BLE001 - explicitly non-authoritative API
            return None

    def _lifecycle_lock_for(self) -> threading.Lock:
        lifecycle_lock = getattr(self, "_lifecycle_lock", None)
        if lifecycle_lock is None:
            # Boundary tests construct minimal instances with ``__new__``.
            lifecycle_lock = threading.Lock()
            self._lifecycle_lock = lifecycle_lock
        return lifecycle_lock

    def _process_snapshot(self) -> subprocess.Popen | None:
        with self._lifecycle_lock_for():
            return self._process

    def _mark_closed_and_snapshot(
        self,
    ) -> tuple[bool, subprocess.Popen | None]:
        """Atomically prevent late publication and capture the active child."""

        with self._lifecycle_lock_for():
            was_closed = self._closed.is_set()
            self._closed.set()
            self._is_ready = False
            return was_closed, self._process

    def request_close(self) -> None:
        """Abort in-flight I/O without waiting for the request serialization lock."""

        _, process = self._mark_closed_and_snapshot()
        # Wake an encoder blocked in ``_receive`` even before process teardown
        # propagates EOF through the launcher thread.
        self._responses.put({"type": "closed"})
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()
            except (OSError, ValueError):
                pass

    def close(self, timeout: float = ROUTER_CLOSE_TOTAL_TIMEOUT_SECONDS) -> None:
        """Prefer a graceful shutdown, then abort within one total deadline."""

        requested_timeout = float(timeout)
        timeout = (
            min(
                MAX_PROCESS_REAP_TIMEOUT_SECONDS,
                max(0.0, requested_timeout),
            )
            if math.isfinite(requested_timeout)
            else 0.0
        )
        started_at = time.monotonic()
        deadline = started_at + timeout
        final_reap_reserve = min(
            timeout,
            ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS,
        )
        graceful_budget = max(0.0, timeout - final_reap_reserve)
        graceful_deadline = started_at + graceful_budget
        lock_timeout = min(
            ROUTER_CLOSE_GRACEFUL_LOCK_TIMEOUT_SECONDS,
            remaining_seconds(
                graceful_deadline,
                graceful_budget,
                now=time.monotonic(),
            ),
        )
        acquired = self._lock.acquire(timeout=lock_timeout)
        if acquired:
            try:
                was_closed, process = self._mark_closed_and_snapshot()
                if not was_closed and process is not None:
                    if process.poll() is None and process.stdin is not None:
                        try:
                            request_id = self._allocate_request_id_locked()
                            self._send({"type": "shutdown", "id": request_id})
                        except (OSError, RuntimeError):
                            pass
            finally:
                self._lock.release()
        else:
            # An encoder owns the lock. Mark closed and kill its transport so
            # ``_receive`` wakes instead of forcing shutdown to inherit 120 s.
            self.request_close()
            process = self._process_snapshot()

        if process is not None:
            try:
                running = process.poll() is None
            except (OSError, ValueError):
                running = True
            if running:
                remaining = remaining_seconds(
                    graceful_deadline,
                    graceful_budget,
                    now=time.monotonic(),
                )
                try:
                    process.wait(timeout=remaining)
                except (
                    OSError,
                    ValueError,
                    subprocess.TimeoutExpired,
                ):
                    self.request_close()

        if process is not None:
            remaining = remaining_seconds(
                deadline,
                timeout,
                now=time.monotonic(),
            )
            status = terminate_and_reap_bounded(
                process,
                timeout=remaining,
                final_wait=min(
                    remaining,
                    ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS / 2.0,
                ),
            )
            report_incomplete_reap(
                ReapResource.ROUTER_PROCESS,
                status,
            )

        launcher = getattr(self, "_launcher", None)
        if (
            launcher is not None
            and launcher is not threading.current_thread()
            and launcher.is_alive()
        ):
            launcher.join(
                timeout=remaining_seconds(
                    deadline,
                    timeout,
                    now=time.monotonic(),
                )
            )


class RequestBudgetEncoder:
    """Apply a short monotonic deadline only on the interactive thread.

    Background corpus and catalog construction run outside a request scope and
    retain the long encoder timeout. Interactive consumers already treat
    encoder errors as advisory misses, so an expired call falls back to their
    lexical path without acquiring routing authority. Exact text rows are
    memoized only for the request lifetime so overlapping batches reuse the
    first embedding bit for bit.
    """

    def __init__(
        self,
        router: ProcessIntentRouter,
        *,
        interactive_timeout: float = (
            DEFAULT_INTERACTIVE_ENCODER_TIMEOUT_SECONDS
        ),
        offline_timeout: float = DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._router = router
        self._interactive_timeout = ProcessIntentRouter._validated_timeout(
            interactive_timeout,
        )
        self._offline_timeout = ProcessIntentRouter._validated_timeout(
            offline_timeout,
        )
        self._request_state = threading.local()

    def begin_request(self, budget_seconds: float) -> None:
        """Start one thread-local budget measured from the monotonic clock."""

        budget = ProcessIntentRouter._validated_timeout(budget_seconds)
        self._request_state.deadline = time.monotonic() + budget
        self._request_state.maximum_timeout = budget
        self._request_state.row_cache = {}

    def end_request(self) -> None:
        """Clear the interactive deadline without affecting background work."""

        if hasattr(self._request_state, "deadline"):
            del self._request_state.deadline
        if hasattr(self._request_state, "maximum_timeout"):
            del self._request_state.maximum_timeout
        if hasattr(self._request_state, "row_cache"):
            del self._request_state.row_cache

    def __call__(self, texts: list[str] | tuple[str, ...]):
        deadline = getattr(self._request_state, "deadline", None)
        if deadline is None:
            return self._router.encode(
                texts,
                timeout=self._offline_timeout,
            )
        maximum_timeout = float(self._request_state.maximum_timeout)
        remaining = remaining_seconds(
            float(deadline),
            maximum_timeout,
            now=time.monotonic(),
        )
        if remaining <= 0.0:
            raise TimeoutError("interactive encoder budget expired")
        batch = ProcessIntentRouter._validated_texts(texts)
        row_cache = self._request_state.row_cache
        if len(batch) == 1:
            cached_row = row_cache.get(batch[0])
            if cached_row is not None:
                return cached_row.reshape(1, -1)
            missing = batch
        else:
            missing = tuple(
                dict.fromkeys(text for text in batch if text not in row_cache)
            )
        if missing:
            encoded = self._router.encode(
                missing,
                timeout=min(self._interactive_timeout, remaining),
            )
            for text, row in zip(missing, encoded, strict=True):
                cached_row = row.copy()
                cached_row.setflags(write=False)
                row_cache[text] = cached_row
            if len(missing) == len(batch):
                return encoded

        rows = [row_cache[text] for text in batch]
        import numpy as np

        return np.stack(rows, axis=0)

    def try_ready(self, timeout: float = 0.0) -> bool:
        """Observe worker readiness without starting or invalidating a request."""

        return self._router.try_ready(timeout)
