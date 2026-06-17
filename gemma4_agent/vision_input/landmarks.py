"""MediaPipe landmark extraction for hands and face.

The detector supports the current MediaPipe Tasks API and keeps a small legacy
path for older wheels that still expose mp.solutions. No video frames are
persisted; only landmark coordinates are returned to the caller.
"""
from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CAMERA_DATA_DIR = Path.home() / ".gemma4" / "camera"
MODEL_DIR = CAMERA_DATA_DIR / "models"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    url: str
    license: str
    model_card_url: str
    # sha256 of the exact bytes that were audited as Apache-2.0 (commercial-OK).
    # Recorded for license traceability + reproducibility. The URL points at the
    # MediaPipe "latest" channel, so if Google republishes the asset the hash will
    # differ; we WARN (not fail) and surface the new hash to be re-audited and
    # re-pinned, rather than bricking the download. Empty = not yet pinned.
    sha256: str = ""


DEFAULT_MODELS: dict[str, ModelSpec] = {
    "hand": ModelSpec(
        name="hand_landmarker.task",
        url="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
        license="Apache-2.0",
        model_card_url="https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf",
        sha256="fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    ),
    "face": ModelSpec(
        name="face_landmarker.task",
        url="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
        license="Apache-2.0",
        model_card_url="https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf",
        sha256="64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
}


@dataclass(frozen=True)
class NormalizedPoint:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class HandSample:
    landmarks: tuple[NormalizedPoint, ...]
    handedness: str = ""
    score: float | None = None


@dataclass(frozen=True)
class FaceSample:
    landmarks: tuple[NormalizedPoint, ...]
    transformation_matrix: tuple[tuple[float, ...], ...] | None = None


@dataclass(frozen=True)
class LandmarkFrame:
    timestamp_ms: int
    hands: tuple[HandSample, ...]
    faces: tuple[FaceSample, ...]
    backend: str

    @property
    def primary_hand(self) -> HandSample | None:
        return self.hands[0] if self.hands else None

    @property
    def primary_face(self) -> FaceSample | None:
        return self.faces[0] if self.faces else None


def ensure_default_models(model_dir: Path | None = None, *, download: bool = False) -> dict[str, Path]:
    target_dir = model_dir or MODEL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    missing: list[str] = []
    for key, spec in DEFAULT_MODELS.items():
        path = target_dir / spec.name
        if not path.is_file():
            if download:
                _download_atomic(spec.url, path, expected_sha256=spec.sha256)
            else:
                missing.append(f"{key}: {path}")
        paths[key] = path
    if missing:
        joined = "; ".join(missing)
        raise FileNotFoundError(
            "missing MediaPipe task models: "
            f"{joined}. Run with --download-models to cache official Apache-2.0 assets."
        )
    return paths


class MediaPipeLandmarkDetector:
    """CPU MediaPipe detector for hands and face landmarks."""

    def __init__(
        self,
        *,
        model_dir: Path | None = None,
        download_models: bool = False,
        num_hands: int = 1,
        min_confidence: float = 0.5,
    ) -> None:
        self.model_dir = model_dir
        self.download_models = download_models
        self.num_hands = num_hands
        self.min_confidence = min_confidence
        self.backend = ""
        self._mp: Any | None = None
        self._vision: Any | None = None
        self._hand: Any | None = None
        self._face: Any | None = None
        self._last_timestamp_ms = -1

    def __enter__(self) -> "MediaPipeLandmarkDetector":
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def start(self) -> None:
        import mediapipe as mp

        self._mp = mp
        # Preferir SIEMPRE la Tasks API: es la soportada (las legacy solutions
        # terminaron soporte en marzo 2023), usa los .task pineados/auditados
        # por sha256 y es la ÚNICA que emite la facial transformation matrix
        # (sin ella el head-pose cae al heurístico 2D, medido mucho más débil
        # en monitores laterales — ver pointer.estimate_head_pose). El orden
        # viejo prefería solutions si existía, dejando la matriz siempre en None.
        tasks_error: Exception | None = None
        try:
            self._start_tasks(mp)
            return
        except FileNotFoundError:
            # Modelos .task ausentes y sin download: error accionable, no caer
            # en silencio a la API deprecada con otros modelos.
            raise
        except Exception as exc:
            tasks_error = exc
        if getattr(mp, "solutions", None) is not None:
            print(
                f"[landmarks] Tasks API failed ({type(tasks_error).__name__}: {tasks_error}); "
                "falling back to legacy mp.solutions (no transformation matrix).",
                flush=True,
            )
            self._start_legacy_solutions(mp)
            return
        raise RuntimeError(
            f"MediaPipe Tasks API failed and no legacy fallback is available: {tasks_error}"
        )

    def detect(self, bgr_frame: Any, timestamp_ms: int, *, run_face: bool = True) -> LandmarkFrame:
        if self._mp is None:
            raise RuntimeError("MediaPipeLandmarkDetector is not started")
        timestamp_ms = self._monotonic_timestamp(timestamp_ms)
        if self.backend == "tasks":
            return self._detect_tasks(bgr_frame, timestamp_ms, run_face=run_face)
        return self._detect_legacy(bgr_frame, timestamp_ms, run_face=run_face)

    def close(self) -> None:
        for detector in (self._hand, self._face):
            close = getattr(detector, "close", None)
            if close is not None:
                close()
        self._hand = None
        self._face = None

    def _start_tasks(self, mp: Any) -> None:
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        paths = ensure_default_models(self.model_dir, download=self.download_models)
        running_mode = vision.RunningMode.VIDEO
        hand_options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(paths["hand"])),
            running_mode=running_mode,
            num_hands=self.num_hands,
            min_hand_detection_confidence=max(0.7, self.min_confidence),
            min_hand_presence_confidence=max(0.7, self.min_confidence),
            min_tracking_confidence=max(0.7, self.min_confidence),
        )
        face_options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(paths["face"])),
            running_mode=running_mode,
            num_faces=1,
            min_face_detection_confidence=self.min_confidence,
            min_face_presence_confidence=self.min_confidence,
            min_tracking_confidence=self.min_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
        )
        self._vision = vision
        self._hand = vision.HandLandmarker.create_from_options(hand_options)
        self._face = vision.FaceLandmarker.create_from_options(face_options)
        self.backend = "tasks"

    def _start_legacy_solutions(self, mp: Any) -> None:
        self._hand = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=self.num_hands,
            min_detection_confidence=self.min_confidence,
            min_tracking_confidence=self.min_confidence,
        )
        self._face = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=self.min_confidence,
            min_tracking_confidence=self.min_confidence,
        )
        self.backend = "solutions"

    def _detect_tasks(self, bgr_frame: Any, timestamp_ms: int, *, run_face: bool) -> LandmarkFrame:
        import cv2
        import numpy as np

        mp = self._mp
        assert mp is not None
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        hand_result = self._hand.detect_for_video(image, timestamp_ms) if self._hand is not None else None
        face_result = self._face.detect_for_video(image, timestamp_ms) if run_face and self._face is not None else None
        hands: list[HandSample] = []
        if hand_result is not None:
            for idx, raw_landmarks in enumerate(hand_result.hand_landmarks or []):
                categories = (hand_result.handedness or [[]])[idx] if idx < len(hand_result.handedness or []) else []
                handedness = categories[0].category_name if categories else ""
                score = float(categories[0].score) if categories else None
                hands.append(HandSample(tuple(_point(p) for p in raw_landmarks), handedness, score))
        faces: list[FaceSample] = []
        if face_result is not None:
            matrices = getattr(face_result, "facial_transformation_matrixes", None) or []
            for idx, raw_landmarks in enumerate(face_result.face_landmarks or []):
                matrix = _matrix_tuple(matrices[idx]) if idx < len(matrices) else None
                faces.append(FaceSample(tuple(_point(p) for p in raw_landmarks), matrix))
        return LandmarkFrame(timestamp_ms, tuple(hands), tuple(faces), self.backend)

    def _detect_legacy(self, bgr_frame: Any, timestamp_ms: int, *, run_face: bool) -> LandmarkFrame:
        import cv2

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        hand_result = self._hand.process(rgb) if self._hand is not None else None
        face_result = self._face.process(rgb) if run_face and self._face is not None else None
        hands: list[HandSample] = []
        raw_hands = getattr(hand_result, "multi_hand_landmarks", None) or []
        raw_handed = getattr(hand_result, "multi_handedness", None) or []
        for idx, raw in enumerate(raw_hands):
            handedness = ""
            score: float | None = None
            if idx < len(raw_handed):
                category = raw_handed[idx].classification[0]
                handedness = str(category.label)
                score = float(category.score)
            hands.append(HandSample(tuple(_point(p) for p in raw.landmark), handedness, score))
        faces = tuple(
            FaceSample(tuple(_point(p) for p in raw.landmark), None)
            for raw in (getattr(face_result, "multi_face_landmarks", None) or [])
        )
        return LandmarkFrame(timestamp_ms, tuple(hands), faces, self.backend)

    def _monotonic_timestamp(self, timestamp_ms: int) -> int:
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms


def _download_atomic(url: str, path: Path, *, expected_sha256: str = "") -> None:
    import hashlib

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            with tmp.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    out.write(chunk)
        got = digest.hexdigest()
        if expected_sha256 and got != expected_sha256:
            # The audited bytes changed upstream (MediaPipe "latest" moved). Don't
            # silently ship un-audited bytes: warn loudly with the new hash so it
            # can be re-audited as commercial-OK and re-pinned in ModelSpec.
            import warnings

            warnings.warn(
                f"sha256 mismatch for {path.name}: expected {expected_sha256}, got {got}. "
                "Re-audit the license of the new asset before shipping, then update ModelSpec.sha256.",
                stacklevel=2,
            )
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _point(raw: Any) -> NormalizedPoint:
    return NormalizedPoint(float(raw.x), float(raw.y), float(getattr(raw, "z", 0.0) or 0.0))


def _matrix_tuple(raw: Any) -> tuple[tuple[float, ...], ...] | None:
    try:
        rows = raw.tolist() if hasattr(raw, "tolist") else raw
        return tuple(tuple(float(v) for v in row) for row in rows)
    except Exception:
        return None
