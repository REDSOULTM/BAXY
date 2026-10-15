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
from collections import OrderedDict, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

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
# E5 is trained asymmetrically: a request carries ``query:`` and the text it
# is matched against carries ``passage:``. Encoding both sides as queries
# collapses the cosine range -- measured offline over the fresh paraphrase
# corpus of goal 03 against the whole authenticated catalogue, the expected
# operation entered the top 28 in 106 of 124 rows that way and in 113 with the
# pair the model expects.
PASSAGE_PREFIX = "passage: "
ENCODER_PREFIXES = {"query": QUERY_PREFIX, "passage": PASSAGE_PREFIX}
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
# Un canal del encoder se retira (y se relanza) sólo si su worker muere, rompe
# el protocolo, encadena este número de fallos seguidos dentro de la ventana, o
# no devuelve una respuesta abandonada dentro del margen (colgado). Una sola
# codificación lenta ya no lo retira (ver ``ProcessIntentRouter``).
ROUTER_FAILURE_STREAK = 3
ROUTER_FAILURE_WINDOW_SECONDS = 30.0
ROUTER_LATE_REPLY_GRACE_SECONDS = 30.0
ROUTER_MAX_RESTARTS = 3
ROUTER_RESTART_DELAY_SECONDS = 0.0
# The first worker starts with the mind (no delay); overridable by
# BAXY_MIND_ROUTER_START_DELAY for measurements.
ROUTER_START_DELAY_SECONDS = 0.0
MAX_ENCODER_BATCH_SIZE = 4_096
MAX_ENCODER_TEXT_CHARS = 4_096
# Una petición interactiva (un paso de computer use, un turno) no espera detrás
# de un lote de fondo entero (pasada r7 del goal v3, 2026-10-08: la promoción del
# catálogo arranca en cuanto E5 queda listo y toma el worker; el primer paso de
# cada misión esperaba ~11–14 s y aun así se quedaba sin encoder, y el segundo
# lo encontraba ocupado: 36 pasos «e5_failed»/«e5_cold» en 21 casos). El fondo
# codifica en trozos de este tamaño y, entre trozo y trozo, cede el worker
# mientras una petición interactiva lo espera, a lo sumo
# ``BACKGROUND_YIELD_SECONDS`` por trozo para que el fondo nunca quede parado.
# Ocho textos: con el banco corriendo un trozo de 32 pasaba de los 0,75 s del
# paso (verificación en vivo, v3-17: el paso seguía «e5_failed» con la
# promoción en curso); en reposo 40 nombres tardan 0,2–0,4 s.
BACKGROUND_ENCODER_CHUNK = 8
BACKGROUND_YIELD_SECONDS = 2.0
# Mientras dura una misión de computer use el fondo no toma el worker entre sus
# pasos (lat-e5, r13a: con la promoción del catálogo en curso, 13 pasos salieron
# «e5_failed» con el presupuesto de 0,75 s agotado detrás de un trozo). Cada paso
# renueva la reserva por estos segundos; vencida (la misión terminó o se quedó
# quieta), el fondo sigue. La espera del fondo queda acotada: una misión tiene
# su propio tope de tiempo y la reserva no se renueva sola.
MISSION_BACKGROUND_HOLD_SECONDS = 15.0
# Ronda 22 (tandas de uso real sobre r20, 2026-10-09: 12 pasos «e5_failed», todos en el tope de 0,75 s con el worker
# listo). Una petición interactiva que pasa de su plazo queda abandonada por su id, pero el worker la termina: sus filas
# se guardan aquí al llegar (validadas por id y forma) y la petición siguiente las usa en vez de codificar otra vez. Antes
# se descartaban y cada paso volvía a pedir los mismos nombres de la vista, otra vez sobre el tope: la regla quedaba
# ciega en todos los pasos aunque el worker contestara medio segundo después.
LATE_ROWS_LIMIT = 4_096
LATE_ROWS_COLLECT_SECONDS = 0.05


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

    def encode(
        self,
        texts: list[str] | tuple[str, ...],
        *,
        prefix: str = "query",
    ):
        marker = ENCODER_PREFIXES[prefix]
        return self._model.encode(
            [marker + text for text in texts],
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

    Una codificación que pasa de su plazo no retira el canal (2026-10-08).
    Antes cualquier timeout lo retiraba para siempre, para que la respuesta
    tardía nunca se leyera como la de otra petición; pero una sola codificación
    lenta (la primera tras cargar E5, o con el PC cargado: medido una vez) dejaba
    toda la vida de la mente en literal, sin emparejamiento semántico en
    computer use ni router en ``turn.decide``. Ahora:

    - la petición vencida queda *abandonada* por su id; la siguiente petición
      descarta primero esa respuesta por id (resultado o error) y no envía nada
      mientras siga pendiente, así que una respuesta tardía nunca se entrega a
      otra petición y el worker no acumula trabajo atrasado; sus filas, si
      llegan bien formadas, se guardan para los mismos textos (``late_rows``,
      ronda 22) y nunca se codifican dos veces;
    - el canal sólo se retira si el worker muere o rompe el protocolo, si
      encadena ``ROUTER_FAILURE_STREAK`` fallos seguidos (timeouts o errores de
      su propia petición) dentro de ``ROUTER_FAILURE_WINDOW_SECONDS``, o si la
      respuesta abandonada no llega en ``ROUTER_LATE_REPLY_GRACE_SECONDS``
      (worker colgado);
    - un canal retirado se relanza con un worker nuevo (cola y ids nuevos; el
      proceso viejo se mata y se recoge fuera del turno) a lo sumo
      ``ROUTER_MAX_RESTARTS`` veces en la vida de la mente; agotados, el canal
      queda retirado para siempre como antes.

    Ninguna espera sale del plazo de la petición: el descarte usa lo que le
    queda y un relanzamiento no bloquea al llamador.
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
        self._late_request_id: int | None = None
        self._late_since = 0.0
        self._late_batch: tuple[str, ...] = ()
        self._late_prefix = "query"
        self._late_rows: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self.last_cause = ""
        self._failure_times: list[float] = []
        self._restarts_left = ROUTER_MAX_RESTARTS
        self._closed = threading.Event()
        self._foreground_for()
        self._launcher = threading.Thread(
            target=self._launch_and_read,
            kwargs={"responses": self._responses},
            name="baxy-router-launcher",
            daemon=True,
        )
        self._launcher.start()

    def _launch_and_read(
        self,
        delay: float | None = None,
        responses: queue.Queue[dict] | None = None,
        previous: subprocess.Popen | None = None,
    ) -> None:
        if responses is None:
            responses = self._responses
        if previous is not None:
            # A relaunch reaps the retired worker here, off the request path.
            status = terminate_and_reap_bounded(
                previous,
                timeout=ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS,
                final_wait=ROUTER_CLOSE_FINAL_REAP_TIMEOUT_SECONDS / 2.0,
            )
            report_incomplete_reap(ReapResource.ROUTER_PROCESS, status)
        if delay is None:
            # Was 3 s (2026-07-30: kept the spawn clear of the llama warmup
            # burst; 0 s showed an unstable first-turn cost then). lat-e5
            # (r13a, 104 missions): those 3 s left E5 loading through the
            # first steps of half the missions (5–15 s each; in the bench
            # every case starts a mind, in real use only the first mission
            # after start pays it). Measured again on 2026-10-08 with the
            # gate's GPU profile (measure_mind_budget.run_profile, clean GPU
            # before each run): first turn.decide 2.16/1.26/1.03 s at 0 s
            # against 1.25/1.46 s at 3 s, catalog ready 16.0–19.3 s against
            # 16.2–18.8 s, turn max 3.3–4.1 s against 4.3–5.1 s, the process
            # tree's VRAM peak 3207.6 MiB in all five: no stable cost left.
            # The worker warms itself up before «ready»
            # (router_worker.WARM_UP_TEXTS), and no turn waits for it (the
            # lexical catalog and the step's no-wait probe cover the load).
            try:
                delay = float(
                    os.environ.get(
                        "BAXY_MIND_ROUTER_START_DELAY",
                        str(ROUTER_START_DELAY_SECONDS),
                    )
                )
            except ValueError:
                delay = ROUTER_START_DELAY_SECONDS
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
            responses.put({"type": "closed"})
            return
        with self._lifecycle_lock_for():
            # ``request_close`` sets the event before entering this small
            # publication section. A child created during shutdown, or for a
            # generation already superseded, is killed locally and never
            # becomes the router's active process.
            if self._closed.is_set() or responses is not self._responses:
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
                responses.put({"type": "closed"})
                return
            self._process = process
        self._read_responses(process, responses)

    def _read_responses(
        self,
        process: subprocess.Popen | None = None,
        responses: queue.Queue[dict] | None = None,
    ) -> None:
        if process is None:
            process = self._process
        if responses is None:
            responses = self._responses
        stream = process.stdout if process is not None else None
        if stream is None:
            responses.put({"type": "closed"})
            return
        try:
            for line in stream:
                try:
                    response = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    responses.put({"type": "protocol.error"})
                    return
                if not isinstance(response, dict):
                    responses.put({"type": "protocol.error"})
                    return
                responses.put(response)
        except OSError:
            pass
        finally:
            responses.put({"type": "closed"})

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
        # A worker already loaded is ready even while another request holds it (live check of the r7 fix, v3-15: a
        # chunk of the catalog's promotion held the lock and the mission's second step read «not ready», went cold
        # and literal). Its own request then waits for the worker within its budget.
        with self._lifecycle_lock_for():
            closed = getattr(self, "_closed", None)
            if (
                getattr(self, "_is_ready", False)
                and not getattr(self, "_failed", False)
                and closed is not None
                and not closed.is_set()
            ):
                return True
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
            except Exception as error:  # noqa: BLE001 - worker died or desynced
                self._retire_channel_locked(type(error).__name__)
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
        """Permanently retire a channel once no relaunch is left."""

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

    def _retire_channel_locked(self, reason: str) -> None:
        """Retire this worker; relaunch a fresh one while relaunches remain.

        The new generation gets its own response queue, so nothing the old
        worker wrote (a late reply, its EOF) can reach a request of the new
        one. The old process is killed now and reaped by the relaunch thread,
        outside the caller's request deadline.
        """

        if self._failed or self._closed.is_set():
            return
        restarts_left = int(getattr(self, "_restarts_left", 0))
        if restarts_left <= 0:
            self._fail_closed_locked(reason)
            return
        responses: queue.Queue[dict] = queue.Queue()
        with self._lifecycle_lock_for():
            if self._closed.is_set():
                return
            previous = self._process
            self._process = None
            self._responses = responses
            self._is_ready = False
        self._restarts_left = restarts_left - 1
        self._failure = reason[:128]
        self._late_request_id = None
        self._late_batch = ()
        self._failure_times = []
        if previous is not None:
            try:
                if previous.poll() is None:
                    previous.kill()
            except (OSError, ValueError):
                pass
        launcher = threading.Thread(
            target=self._launch_and_read,
            kwargs={
                "delay": ROUTER_RESTART_DELAY_SECONDS,
                "responses": responses,
                "previous": previous,
            },
            name="baxy-router-relauncher",
            daemon=True,
        )
        self._launcher = launcher
        launcher.start()

    def _count_failure_locked(self, reason: str) -> None:
        """One more failure of a request the worker received; a short streak retires."""

        now = time.monotonic()
        streak = [
            at
            for at in getattr(self, "_failure_times", [])
            if now - at <= ROUTER_FAILURE_WINDOW_SECONDS
        ]
        streak.append(now)
        self._failure_times = streak
        if len(streak) >= ROUTER_FAILURE_STREAK:
            self._retire_channel_locked(f"streak:{reason}")

    def _drain_late_reply_locked(self, deadline: float, timeout: float) -> None:
        """Discard the abandoned request's reply by its id before sending anything.

        While it is still pending nothing is sent: the request times out
        without queueing more work behind a slow worker, and without counting
        as a new failure. A reply overdue past the grace means a hung worker.
        """

        while self._late_request_id is not None:
            try:
                response = self._receive(self._remaining(deadline, timeout))
            except TimeoutError:
                if (
                    time.monotonic() - self._late_since
                    >= ROUTER_LATE_REPLY_GRACE_SECONDS
                ):
                    self._retire_channel_locked("late_reply_overdue")
                raise
            response_id = response.get("id")
            if (
                response.get("type") in {"encode.result", "error"}
                and isinstance(response_id, int)
                and not isinstance(response_id, bool)
                and response_id == self._late_request_id
            ):
                self._late_request_id = None
                if response.get("type") == "encode.result":
                    self._keep_late_rows_locked(response.get("rows"))
                self._late_batch = ()
                continue
            raise RuntimeError("router worker returned a mismatched response")

    def _keep_late_rows_locked(self, rows: object) -> None:
        """Keep the rows of an abandoned request whose reply arrived (ronda 22): its texts are the ones it sent."""

        import numpy as np

        batch = tuple(getattr(self, "_late_batch", ()) or ())
        prefix = str(getattr(self, "_late_prefix", "query"))
        self._late_batch = ()
        if not batch:
            return
        try:
            matrix = np.asarray(rows, dtype=np.float32)
        except (TypeError, ValueError):
            return
        if not (
            matrix.ndim == 2
            and matrix.shape[0] == len(batch)
            and 1 <= matrix.shape[1] <= 4_096
            and bool(np.isfinite(matrix).all())
        ):
            return
        store = getattr(self, "_late_rows", None)
        if store is None:
            store = OrderedDict()
            self._late_rows = store
        for text, row in zip(batch, matrix):
            kept = row.copy()
            kept.setflags(write=False)
            store[(prefix, text)] = kept
            store.move_to_end((prefix, text))
        while len(store) > LATE_ROWS_LIMIT:
            store.popitem(last=False)

    def late_rows(
        self, texts: list[str] | tuple[str, ...], prefix: str = "query",
    ) -> dict[str, Any]:
        """The kept rows of abandoned requests for ``texts`` (ronda 22), after collecting a late reply that already
        arrived. Never waits for the worker: a channel in use or a reply still pending give what is kept."""

        lock = getattr(self, "_lock", None)
        if (
            getattr(self, "_late_request_id", None) is not None
            and lock is not None
            and lock.acquire(blocking=False)
        ):
            try:
                if (
                    self._late_request_id is not None
                    and not self._failed
                    and not self._closed.is_set()
                ):
                    if not self._responses.empty():
                        # The reply already waits in the queue: read with the drain's own rules (by id), at once.
                        try:
                            self._drain_late_reply_locked(
                                time.monotonic() + LATE_ROWS_COLLECT_SECONDS,
                                LATE_ROWS_COLLECT_SECONDS,
                            )
                        except TimeoutError:
                            pass
                        except Exception as error:  # noqa: BLE001 - worker died or desynced
                            self._retire_channel_locked(type(error).__name__)
            finally:
                lock.release()
        store = getattr(self, "_late_rows", None)
        if not store:
            return {}
        found: dict[str, Any] = {}
        for text in texts:
            row = store.get((prefix, text))
            if row is not None:
                found[text] = row
        return found

    def _receive_reply_locked(
        self,
        request_id: int,
        deadline: float,
        timeout: float,
    ) -> dict:
        response = self._receive(self._remaining(deadline, timeout))
        response_id = response.get("id")
        if (
            isinstance(response_id, bool)
            or response_id != request_id
            or (
                not (
                    response.get("type") == "encode.result"
                    and set(response) == {"type", "id", "rows"}
                )
                and not (
                    response.get("type") == "error"
                    and set(response) == {"type", "id", "code"}
                )
            )
        ):
            raise RuntimeError("router worker returned a mismatched response")
        return response

    def _ensure_usable_locked(self) -> None:
        if self._failed:
            raise RuntimeError("router worker is permanently unavailable")
        if self._closed.is_set():
            raise RuntimeError("router worker is closed")

    def encode(
        self,
        texts: list[str] | tuple[str, ...],
        timeout: float = DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS,
        *,
        prefix: str = "query",
    ):
        import numpy as np

        if prefix not in ENCODER_PREFIXES:
            raise ValueError("encoder prefix is invalid")
        batch = self._validated_texts(texts)
        timeout = self._validated_timeout(timeout)
        deadline = time.monotonic() + timeout
        # Why the last request failed (ronda 22), for the encoder's trace: «busy» (another request held the worker),
        # «loading», «late_pending» (the previous abandoned reply had not arrived), «timeout» (its own encoding),
        # «error», «invalid_rows», «unavailable» or the retire reason.
        self.last_cause = "busy"
        if not self._lock.acquire(timeout=timeout):
            raise TimeoutError("router worker is busy")
        try:
            self.last_cause = "unavailable"
            self._ensure_usable_locked()
            self.last_cause = "loading"
            # Esperar a que el worker termine de cargar no es un desajuste de
            # protocolo: no se ha enviado nada, así que el canal sigue
            # sincronizado. Tratarlo como tal retiraba el router para siempre
            # cuando el primer turno llegaba dentro de los ~14 s que tarda E5
            # en cargar, y el catálogo se quedaba en su ranking léxico durante
            # toda la vida del proceso. Ése era el fallo que dejaba la
            # recuperación en 73/124 sobre el corpus de paráfrasis del goal 03,
            # contra 102/124 una vez que el intercambio ocurre de verdad.
            try:
                self._wait_ready(self._remaining(deadline, timeout))
            except TimeoutError:
                raise
            except Exception as error:  # noqa: BLE001 - worker died at launch
                self.last_cause = f"retired:{type(error).__name__}"
                self._retire_channel_locked(type(error).__name__)
                raise
            try:
                self.last_cause = "late_pending"
                self._drain_late_reply_locked(deadline, timeout)
                self.last_cause = "timeout"
                request_id = self._allocate_request_id_locked()
                self._send(
                    {
                        "type": "encode",
                        "id": request_id,
                        "texts": list(batch),
                        "prefix": prefix,
                    }
                )
                try:
                    response = self._receive_reply_locked(
                        request_id,
                        deadline,
                        timeout,
                    )
                except TimeoutError:
                    # Abandoned by id: its reply is discarded by the next
                    # request and never read as anyone else's.
                    self._late_request_id = request_id
                    self._late_since = time.monotonic()
                    self._late_batch = batch
                    self._late_prefix = prefix
                    self._count_failure_locked("timeout")
                    raise
            except TimeoutError:
                raise
            except Exception as error:  # noqa: BLE001 - worker died or desynced
                self.last_cause = f"retired:{type(error).__name__}"
                self._retire_channel_locked(type(error).__name__)
                if isinstance(error, RuntimeError):
                    raise
                raise RuntimeError("router worker protocol failed") from error
            # The reply carries this request's id: the channel is in sync, so a
            # bad answer is one failure of this request, not a desync.
            if response.get("type") == "error":
                self.last_cause = "error"
                self._count_failure_locked("error")
                raise RuntimeError("router worker could not encode the batch")
            try:
                matrix = np.asarray(response["rows"], dtype=np.float32)
                valid = (
                    matrix.ndim == 2
                    and matrix.shape[0] == len(batch)
                    and 1 <= matrix.shape[1] <= 4_096
                    and bool(np.isfinite(matrix).all())
                )
            except (TypeError, ValueError):
                valid = False
            if not valid:
                self.last_cause = "invalid_rows"
                self._count_failure_locked("invalid_rows")
                raise RuntimeError("router worker returned invalid embeddings")
            self._failure_times = []
            self.last_cause = ""
            return matrix
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

    def _foreground_for(self) -> threading.Condition:
        foreground = getattr(self, "_foreground", None)
        if foreground is None:
            # Boundary tests construct minimal instances with ``__new__``.
            foreground = threading.Condition(threading.Lock())
            self._foreground_waiting = 0
            self._foreground = foreground
        return foreground

    @contextmanager
    def foreground(self) -> Iterator[None]:
        """Mark an interactive request while it waits for (and uses) the worker: background batches yield to it."""

        foreground = self._foreground_for()
        with foreground:
            self._foreground_waiting += 1
        try:
            yield
        finally:
            with foreground:
                self._foreground_waiting -= 1
                if self._foreground_waiting <= 0:
                    foreground.notify_all()

    def hold_background(self, seconds: float = MISSION_BACKGROUND_HOLD_SECONDS) -> None:
        """A computer-use mission is under way: background batches leave the worker to it for ``seconds`` from now
        (each step renews it; never shortened by a later, shorter hold)."""

        foreground = self._foreground_for()
        until = time.monotonic() + max(0.0, float(seconds))
        with foreground:
            if until > getattr(self, "_held_until", 0.0):
                self._held_until = until

    def release_background(self) -> None:
        """The mission ended: background batches may take the worker again at once."""

        foreground = self._foreground_for()
        with foreground:
            self._held_until = 0.0
            foreground.notify_all()

    def yield_to_foreground(self, timeout: float = BACKGROUND_YIELD_SECONDS) -> bool:
        """A background batch waits, at most ``timeout``, while an interactive request is marked, and while a mission
        holds the worker (``hold_background``) until that hold runs out; True if neither is."""

        foreground = self._foreground_for()
        deadline = time.monotonic() + max(0.0, float(timeout))
        closed = getattr(self, "_closed", None)
        with foreground:
            while True:
                now = time.monotonic()
                held = getattr(self, "_held_until", 0.0) - now
                if held > 0.0 and not (closed is not None and closed.is_set()):
                    # The mission's hold: waited out whole, bounded by itself (only a step renews it); a closing
                    # router is seen within a short slice.
                    foreground.wait(min(held, 0.25))
                    continue
                if self._foreground_waiting <= 0:
                    return True
                left = deadline - now
                if left <= 0.0:
                    return False
                foreground.wait(left)

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


def _capture_encoder_call_timing(
    *, texts: int, reused: int, prefix: str, elapsed_ms: float, budget_ms: float, cause: str,
) -> None:
    """Append an opt-in, content-free row for one interactive encoder call (ronda 22), beside the model's rows
    (``BAXY_MIND_MODEL_CALL_AUDIT_PATH``): the r20 tandas said «e5_failed» and nothing of why."""

    configured = os.environ.get("BAXY_MIND_MODEL_CALL_AUDIT_PATH", "").strip()
    if not configured:
        return
    try:
        record = {
            "schema": "baxy.encoder-call-timing.v1",
            "thread": threading.current_thread().name,
            "prefix": prefix,
            "texts": int(texts),
            "reused_late": int(reused),
            "elapsed_ms": round(float(elapsed_ms), 1),
            "budget_ms": round(float(budget_ms), 1),
            "outcome": "failed" if cause else "ok",
            "cause": cause,
        }
        path = Path(configured).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except (OSError, ValueError, TypeError):
        # Opt-in diagnostics never change the step.
        return


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
        # Why this encoder's last interactive call failed (ronda 22), «» after one that answered.
        self.last_cause = ""

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

    def __call__(
        self,
        texts: list[str] | tuple[str, ...],
        *,
        prefix: str = "query",
    ):
        deadline = getattr(self._request_state, "deadline", None)
        if deadline is None:
            return self._background_encode(texts, prefix)
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
            cached_row = row_cache.get((prefix, batch[0]))
            if cached_row is not None:
                return cached_row.reshape(1, -1)
            missing = batch
        else:
            missing = tuple(
                dict.fromkeys(
                    text for text in batch if (prefix, text) not in row_cache
                )
            )
        late = self._late_rows(missing, prefix) if missing else {}
        if late:
            # Ronda 22: what an abandoned request of an earlier step encoded after its deadline is used, never encoded
            # again past the step's deadline.
            for text, row in late.items():
                row_cache[(prefix, text)] = row
            missing = tuple(text for text in missing if text not in late)
        if missing:
            started = time.monotonic()
            call_timeout = min(self._interactive_timeout, remaining)
            cause = ""
            try:
                with self._foreground():
                    encoded = self._router.encode(
                        missing,
                        timeout=call_timeout,
                        prefix=prefix,
                    )
            except Exception as error:
                cause = str(getattr(self._router, "last_cause", "") or type(error).__name__)
                self.last_cause = cause
                raise
            finally:
                _capture_encoder_call_timing(
                    texts=len(missing),
                    reused=len(late),
                    prefix=prefix,
                    elapsed_ms=(time.monotonic() - started) * 1000.0,
                    budget_ms=call_timeout * 1000.0,
                    cause=cause,
                )
            self.last_cause = ""
            for text, row in zip(missing, encoded, strict=True):
                cached_row = row.copy()
                cached_row.setflags(write=False)
                row_cache[(prefix, text)] = cached_row
            if len(missing) == len(batch) and not late:
                return encoded

        rows = [row_cache[(prefix, text)] for text in batch]
        import numpy as np

        return np.stack(rows, axis=0)

    def _late_rows(self, texts: tuple[str, ...], prefix: str) -> dict[str, Any]:
        collect = getattr(self._router, "late_rows", None)
        if not callable(collect):
            return {}
        try:
            found = collect(texts, prefix)
        except Exception:  # noqa: BLE001 - kept rows are advisory like the encoder
            return {}
        return found if isinstance(found, dict) else {}

    def try_ready(self, timeout: float = 0.0) -> bool:
        """Observe worker readiness without starting or invalidating a request; a background batch yields to it."""

        with self._foreground():
            return self._router.try_ready(timeout)

    def _foreground(self) -> Any:
        mark = getattr(self._router, "foreground", None)
        return mark() if callable(mark) else nullcontext()

    def _background_encode(self, texts: list[str] | tuple[str, ...], prefix: str) -> Any:
        """A batch outside a request, in chunks that yield the worker to an interactive request between them."""

        batch = list(texts) if isinstance(texts, (list, tuple)) else texts
        step = BACKGROUND_ENCODER_CHUNK
        yield_to = getattr(self._router, "yield_to_foreground", None)
        if not isinstance(batch, list) or len(batch) <= step or not callable(yield_to):
            if callable(yield_to):
                # A small batch yields too: a mission's hold covers every background batch (lat-e5).
                yield_to(BACKGROUND_YIELD_SECONDS)
            return self._router.encode(texts, timeout=self._offline_timeout, prefix=prefix)
        import numpy as np

        parts = []
        for start in range(0, len(batch), step):
            yield_to(BACKGROUND_YIELD_SECONDS)
            parts.append(self._router.encode(batch[start:start + step], timeout=self._offline_timeout, prefix=prefix))
        return np.concatenate(parts, axis=0)
