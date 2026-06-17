"""OpenCV webcam capture helpers for the camera-control POC."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

# MSMF + hardware transforms tarda DECENAS de segundos en abrir muchas webcams
# (MEDIDO en esta máquina: open 28.1s -> el run de 6s terminaba con 0 frames).
# Workaround oficial de OpenCV: deshabilitar los HW transforms del backend MSMF
# (opencv/opencv#17687, fix #20327). Leído por OpenCV al crear el capture, así
# que alcanza con fijarlo antes de cv2.VideoCapture; setdefault respeta un
# override externo. Tras el fix: open 0.4s frío / 0.1s caliente (medido).
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")


@dataclass(frozen=True)
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    backend: int | None = None
    # Drop the capture queue to 1 so read() returns the freshest frame instead
    # of the oldest buffered one (lower frame->cursor latency). Some MSMF
    # backends ignore this; measure in vivo before assuming it took effect.
    drop_stale_frames: bool = True
    # Transient UVC glitches return ok=False for a frame or two. Retry briefly
    # rather than tearing down the whole control loop on one bad read.
    read_retries: int = 3
    read_retry_sleep_s: float = 0.005
    # El PRIMER frame es distinto: open() puede devolver OK y el streaming
    # tardar cientos de ms en arrancar (o fallar con MF_E_HW_MFT_FAILED_START_
    # STREAMING si otra app tiene la cámara). Presupuesto de paciencia propio,
    # por tiempo y no por intentos (medido: 3×5ms moría en arranques fríos).
    first_read_timeout_s: float = 3.0


@dataclass(frozen=True)
class CameraFrame:
    bgr: Any
    timestamp_s: float
    sequence: int


class OpenCVCamera:
    """Small context-managed wrapper around cv2.VideoCapture."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._cv2: Any | None = None
        self._cap: Any | None = None
        self._sequence = 0

    def __enter__(self) -> "OpenCVCamera":
        self.open()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def open(self) -> None:
        import cv2

        self._cv2 = cv2
        if self.config.backend is None:
            cap = cv2.VideoCapture(self.config.index)
        else:
            cap = cv2.VideoCapture(self.config.index, self.config.backend)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"cannot open camera index {self.config.index}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.config.width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.config.height))
        cap.set(cv2.CAP_PROP_FPS, float(self.config.fps))
        if self.config.drop_stale_frames:
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
        self._cap = cap

    def read(self) -> CameraFrame:
        if self._cap is None:
            raise RuntimeError("camera is not open")
        if self._sequence == 0:
            return self._read_first_frame()
        attempts = max(1, int(self.config.read_retries))
        for attempt in range(attempts):
            ok, frame = self._cap.read()
            if ok and frame is not None:
                self._sequence += 1
                return CameraFrame(bgr=frame, timestamp_s=time.perf_counter(), sequence=self._sequence)
            # A disconnected camera is fatal; a transient glitch is not. Only
            # retry while the device still reports open.
            if not self._cap.isOpened():
                raise RuntimeError(f"camera index {self.config.index} disconnected")
            if attempt < attempts - 1 and self.config.read_retry_sleep_s > 0:
                time.sleep(self.config.read_retry_sleep_s)
        raise RuntimeError("camera frame read failed after retries")

    def _read_first_frame(self) -> CameraFrame:
        """Primer frame con presupuesto por TIEMPO: el streaming puede tardar
        en arrancar tras open(), y si otra app tiene la cámara el fallo debe
        ser accionable, no un "failed after retries" críptico."""
        if self._cap is None:
            raise RuntimeError("camera is not open")
        deadline = time.perf_counter() + max(0.1, float(self.config.first_read_timeout_s))
        while True:
            ok, frame = self._cap.read()
            if ok and frame is not None:
                self._sequence += 1
                return CameraFrame(bgr=frame, timestamp_s=time.perf_counter(), sequence=self._sequence)
            if not self._cap.isOpened():
                raise RuntimeError(f"camera index {self.config.index} disconnected")
            if time.perf_counter() >= deadline:
                raise RuntimeError(
                    f"camera index {self.config.index} opened but never delivered a frame "
                    f"in {self.config.first_read_timeout_s:.1f}s — otra aplicación puede "
                    "estar usando la cámara (Zoom/Teams/etc.); cerrala y reintentá."
                )
            time.sleep(0.05)

    def info(self) -> dict[str, Any]:
        if self._cap is None:
            raise RuntimeError("camera is not open")
        cv2 = self._cv2
        cap = self._cap
        backend_name = "unknown"
        get_backend_name = getattr(cap, "getBackendName", None)
        if get_backend_name is not None:
            try:
                backend_name = str(get_backend_name())
            except Exception:
                backend_name = "unknown"
        return {
            "index": self.config.index,
            "requested_width": self.config.width,
            "requested_height": self.config.height,
            "requested_fps": self.config.fps,
            "requested_backend_code": self.config.backend,
            "opencv_backend": backend_name,
            "actual_width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) if cv2 is not None else 0,
            "actual_height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) if cv2 is not None else 0,
            "actual_fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0) if cv2 is not None else 0.0,
        }

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
