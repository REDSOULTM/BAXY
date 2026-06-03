"""Phase 0 webcam POC runner.

Run:
    python -m gemma4_agent.vision_input.poc --download-models
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .camera import CameraConfig, OpenCVCamera
from .gaze import GazeRefinementConfig
from .gestures import GestureResult, GestureStabilizer, recognize_hand_gesture
from .landmarks import DEFAULT_MODELS, CAMERA_DATA_DIR, LandmarkFrame, MediaPipeLandmarkDetector
from .monitors import canvas_to_dict, virtual_canvas
from .pointer import HeadPointerEstimate, HeadPointerMapper, frame_delta_rms_px, jitter_rms_px


LABEL_KEYS = {
    ord("1"): "fist",
    ord("2"): "pinch",
    ord("3"): "palm",
    ord("4"): "point",
}
NUMPAD_LABEL_KEYS = {
    0x61: "fist",
    0x62: "pinch",
    0x63: "palm",
    0x64: "point",
}
KEY_CLEAR = {ord("0"), 0x60}
KEY_RESET = {ord("r"), ord("R")}
KEY_QUIT = {ord("q"), ord("Q"), 27}
EVAL_LABELS = ("fist", "pinch", "palm", "point")
GATE_LABELS = ("fist", "pinch", "palm")
PREDICTION_LABELS = ("fist", "pinch", "palm", "point", "two_fingers", "unknown", "none")
DEFAULT_CAMERA_INDEX = 0
DEFAULT_CAMERA_BACKEND = "msmf"
# 1280x720 instead of 640x480: more facial-landmark detail -> finer, less noisy
# head pose, which feeds calibration. The camera falls back to its nearest
# supported mode if it can't deliver 720p.
DEFAULT_CAMERA_WIDTH = 1280
DEFAULT_CAMERA_HEIGHT = 720
DEFAULT_FACE_EVERY_N = 4
DEFAULT_SAMPLES_PER_GESTURE = 10
DEFAULT_JITTER_SETTLE_SECONDS = 1.0
DEFAULT_JITTER_SECONDS = 3.0


def main(argv: list[str] | None = None) -> int:
    from .dpi import ensure_dpi_awareness

    ensure_dpi_awareness()
    args = _parse_args(argv)
    if args.list_cameras:
        print(json.dumps(list_cameras(args), indent=2, sort_keys=True))
        return 0
    report = run_phase0(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def run_phase0(args: argparse.Namespace) -> dict[str, Any]:
    import cv2

    canvas = virtual_canvas()
    mapper = HeadPointerMapper(
        canvas,
        GazeRefinementConfig(
            enabled=args.iris_refine,
            gain_x=args.gaze_gain_x,
            gain_y=args.gaze_gain_y,
            deadzone=args.gaze_deadzone,
        ),
        auto_center=not args.no_auto_center,
        center_alpha=args.auto_center_alpha,
    )
    stabilizer = GestureStabilizer(window=args.stabilizer_window)
    active_label: str | None = None
    confusion = _empty_confusion()
    processing_ms: list[float] = []
    pointer_samples: list[tuple[float, float]] = []
    raw_pointer_samples: list[tuple[float, float]] = []
    steady_pointer_samples: list[tuple[float, float]] = []
    steady_raw_pointer_samples: list[tuple[float, float]] = []
    frames = 0
    measured_frames = 0
    camera_info: dict[str, Any] = {}
    last_face = None
    samples_complete_at: float | None = None
    started = time.perf_counter()
    warmup_until = started + args.warmup_seconds
    window = "Gemma 4 Camera Control - Phase 0 POC"
    global_keys = WindowsGlobalKeyPoller()

    camera_config = CameraConfig(
        args.camera_index,
        args.width,
        args.height,
        args.camera_fps,
        backend=_camera_backend_value(args.camera_backend),
    )
    with OpenCVCamera(camera_config) as camera, MediaPipeLandmarkDetector(
        model_dir=args.model_dir,
        download_models=args.download_models,
        num_hands=args.num_hands,
        min_confidence=args.min_confidence,
    ) as detector:
        camera_info = camera.info()
        camera_label = _camera_label(camera_info, args.camera_backend)
        window = f"Gemma 4 Camera Control - {camera_label}"
        if not args.no_window:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        started = time.perf_counter()
        warmup_until = started + args.warmup_seconds
        while True:
            loop_now = time.perf_counter()
            if args.duration > 0 and loop_now - started >= args.duration:
                break
            frame = camera.read()
            bgr = cv2.flip(frame.bgr, 1) if args.mirror else frame.bgr
            timestamp_ms = int(frame.timestamp_s * 1000)
            detect_start = time.perf_counter()
            run_face = frames % max(1, args.face_every_n) == 0
            landmarks = detector.detect(bgr, timestamp_ms, run_face=run_face)
            processing_ms.append((time.perf_counter() - detect_start) * 1000.0)
            frames += 1
            if landmarks.primary_face is not None:
                last_face = landmarks.primary_face
            gesture = recognize_hand_gesture(landmarks.primary_hand)
            stable_label = stabilizer.update(gesture.label)
            head = mapper.update(last_face, frame.timestamp_s)

            measuring = frame.timestamp_s >= warmup_until
            if measuring:
                measured_frames += 1
                if head is not None:
                    pointer_samples.append((head.filtered_x, head.filtered_y))
                    raw_pointer_samples.append((head.raw_x, head.raw_y))
                if active_label is not None and _row_total(confusion[active_label]) < args.samples_per_gesture:
                    prediction = stable_label if stable_label in PREDICTION_LABELS else "unknown"
                    confusion[active_label][prediction] += 1

            fps = measured_frames / max(1e-6, time.perf_counter() - max(started, warmup_until))
            samples_complete = _collection_samples_complete(confusion, args.samples_per_gesture)
            if samples_complete and samples_complete_at is None:
                samples_complete_at = frame.timestamp_s
            jitter_state, jitter_progress = _jitter_state(samples_complete_at, frame.timestamp_s, args)
            if measuring and jitter_state == "measuring" and head is not None:
                steady_pointer_samples.append((head.filtered_x, head.filtered_y))
                steady_raw_pointer_samples.append((head.raw_x, head.raw_y))
            if not args.no_window:
                annotated = _draw_overlay(
                    bgr.copy(),
                    landmarks,
                    gesture,
                    stable_label,
                    head,
                    fps,
                    active_label,
                    confusion,
                    args.samples_per_gesture,
                    canvas.layout_hash,
                    camera_label,
                    samples_complete,
                    jitter_state,
                    jitter_progress,
                    len(steady_pointer_samples),
                )
                cv2.imshow(window, annotated)
                key = cv2.waitKey(1) & 0xFF
                should_quit, active_label, confusion = _apply_key_actions(
                    [key, *global_keys.pressed_keys()],
                    active_label,
                    confusion,
                    stabilizer,
                )
                if not _collection_samples_complete(confusion, args.samples_per_gesture):
                    samples_complete_at = None
                    steady_pointer_samples.clear()
                    steady_raw_pointer_samples.clear()
                if should_quit:
                    break

            if args.stop_when_samples_complete and args.no_window and samples_complete and jitter_state == "complete":
                break

    if not args.no_window:
        cv2.destroyWindow(window)

    ended = time.perf_counter()
    report = _build_report(
        args=args,
        canvas=canvas,
        frames=frames,
        measured_frames=measured_frames,
        elapsed_s=ended - started,
        measured_elapsed_s=max(0.0, ended - max(started, warmup_until)),
        processing_ms=processing_ms,
        confusion=confusion,
        pointer_samples=pointer_samples,
        raw_pointer_samples=raw_pointer_samples,
        steady_pointer_samples=steady_pointer_samples,
        steady_raw_pointer_samples=steady_raw_pointer_samples,
        camera_info=camera_info,
    )
    _write_reports(report, args.report_path)
    return report


def _draw_overlay(
    frame: Any,
    landmarks: LandmarkFrame,
    gesture: GestureResult,
    stable_label: str,
    head: HeadPointerEstimate | None,
    fps: float,
    active_label: str | None,
    confusion: dict[str, dict[str, int]],
    samples_per_gesture: int,
    layout_hash: str,
    camera_label: str,
    samples_complete: bool,
    jitter_state: str,
    jitter_progress: float,
    jitter_samples: int,
) -> Any:
    import cv2

    h, w = frame.shape[:2]
    _draw_hands(frame, landmarks)
    _draw_face(frame, landmarks)
    color = (0, 220, 0)
    cv2.rectangle(frame, (0, 0), (w, 188), (0, 0, 0), -1)
    cv2.putText(frame, f"CAMERA ACTIVE - {camera_label}", (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
    cv2.putText(
        frame,
        f"FPS {fps:5.1f} | gesture {gesture.label} -> {stable_label} | backend {landmarks.backend}",
        (16, 56),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (255, 255, 255),
        1,
    )
    head_text = "head none"
    if head is not None:
        head_text = (
            f"head {head.region} m{head.monitor.index} "
            f"({head.filtered_x:.0f},{head.filtered_y:.0f}) yaw {head.yaw:+.2f} "
            f"pitch {head.pitch:+.2f} src {head.source}"
        )
    cv2.putText(frame, head_text, (16, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    label_text = "label: none"
    if active_label is not None:
        label_text = f"label: {active_label} {_row_total(confusion[active_label])}/{samples_per_gesture}"
    cv2.putText(
        frame,
        f"{label_text} | 1 fist 2 pinch 3 palm 4 point 0 stop r reset q quit | layout {layout_hash}",
        (16, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        (210, 210, 210),
        1,
    )
    cv2.putText(
        frame,
        _progress_text(confusion, samples_per_gesture, ("fist", "pinch")),
        (16, 130),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (220, 220, 220),
        1,
    )
    cv2.putText(
        frame,
        _progress_text(confusion, samples_per_gesture, ("palm", "point")),
        (16, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (220, 220, 220),
        1,
    )
    cv2.putText(
        frame,
        "Imagen actual = camara activa medida",
        (w - 330, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (170, 170, 170),
        1,
    )
    if samples_complete:
        jitter_pct = int(round(jitter_progress * 100))
        if jitter_state == "settling":
            message = "GESTOS OK - cabeza quieta, preparando jitter"
        elif jitter_state == "measuring":
            message = f"JITTER CABEZA QUIETA {jitter_pct:3d}% | muestras {jitter_samples}"
        else:
            message = "JITTER OK - q/Esc guarda reporte y cierra"
        cv2.putText(
            frame,
            message,
            (16, 174),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (0, 220, 255),
            1,
        )
    return frame


def _jitter_state(samples_complete_at: float | None, now_s: float, args: argparse.Namespace) -> tuple[str, float]:
    if samples_complete_at is None:
        return ("waiting", 0.0)
    settle_s = max(0.0, float(args.jitter_settle_seconds))
    measure_s = max(0.0, float(args.jitter_seconds))
    elapsed = max(0.0, now_s - samples_complete_at)
    if elapsed < settle_s:
        return ("settling", 0.0)
    if measure_s <= 0.0:
        return ("complete", 1.0)
    progress = (elapsed - settle_s) / measure_s
    if progress < 1.0:
        return ("measuring", max(0.0, progress))
    return ("complete", 1.0)


class WindowsGlobalKeyPoller:
    """Edge-triggered key polling so OpenCV window focus is not required."""

    def __init__(self) -> None:
        try:
            import win32api

            self._get_async_key_state = win32api.GetAsyncKeyState
        except Exception:
            self._get_async_key_state = None
        self._watch = tuple(sorted(set(LABEL_KEYS) | set(NUMPAD_LABEL_KEYS) | KEY_CLEAR | KEY_RESET | KEY_QUIT))
        self._down: dict[int, bool] = {key: False for key in self._watch}

    def pressed_keys(self) -> list[int]:
        if self._get_async_key_state is None:
            return []
        pressed: list[int] = []
        for key in self._watch:
            is_down = bool(self._get_async_key_state(key) & 0x8000)
            if is_down and not self._down.get(key, False):
                pressed.append(key)
            self._down[key] = is_down
        return pressed


def _apply_key_actions(
    keys: list[int],
    active_label: str | None,
    confusion: dict[str, dict[str, int]],
    stabilizer: GestureStabilizer,
) -> tuple[bool, str | None, dict[str, dict[str, int]]]:
    should_quit = False
    for key in keys:
        if key < 0 or key == 255:
            continue
        if key in KEY_QUIT:
            should_quit = True
        elif key in KEY_CLEAR:
            active_label = None
        elif key in KEY_RESET:
            confusion = _empty_confusion()
            active_label = None
            stabilizer.reset()
        elif key in LABEL_KEYS:
            active_label = LABEL_KEYS[key]
        elif key in NUMPAD_LABEL_KEYS:
            active_label = NUMPAD_LABEL_KEYS[key]
    return should_quit, active_label, confusion


def _draw_hands(frame: Any, landmarks: LandmarkFrame) -> None:
    import cv2

    h, w = frame.shape[:2]
    connections = (
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (0, 9), (9, 10), (10, 11), (11, 12),
        (0, 13), (13, 14), (14, 15), (15, 16),
        (0, 17), (17, 18), (18, 19), (19, 20),
        (5, 9), (9, 13), (13, 17),
    )
    for hand in landmarks.hands:
        pts = [(int(p.x * w), int(p.y * h)) for p in hand.landmarks]
        for a, b in connections:
            if a < len(pts) and b < len(pts):
                cv2.line(frame, pts[a], pts[b], (0, 190, 255), 2)
        for pt in pts:
            cv2.circle(frame, pt, 3, (0, 255, 255), -1)


def _draw_face(frame: Any, landmarks: LandmarkFrame) -> None:
    import cv2

    h, w = frame.shape[:2]
    key = {1, 10, 33, 133, 152, 263, 362}
    for face in landmarks.faces:
        for idx, p in enumerate(face.landmarks):
            if idx in key or idx % 18 == 0:
                cv2.circle(frame, (int(p.x * w), int(p.y * h)), 1, (255, 180, 80), -1)


def _build_report(
    *,
    args: argparse.Namespace,
    canvas: Any,
    frames: int,
    measured_frames: int,
    elapsed_s: float,
    measured_elapsed_s: float,
    processing_ms: list[float],
    confusion: dict[str, dict[str, int]],
    pointer_samples: list[tuple[float, float]],
    raw_pointer_samples: list[tuple[float, float]],
    steady_pointer_samples: list[tuple[float, float]],
    steady_raw_pointer_samples: list[tuple[float, float]],
    camera_info: dict[str, Any],
) -> dict[str, Any]:
    fps = measured_frames / measured_elapsed_s if measured_elapsed_s > 0 else 0.0
    gesture_accuracy = _gesture_accuracy(confusion)
    session_jitter = jitter_rms_px(pointer_samples)
    session_raw_jitter = jitter_rms_px(raw_pointer_samples)
    steady_jitter = jitter_rms_px(steady_pointer_samples)
    steady_raw_jitter = jitter_rms_px(steady_raw_pointer_samples)
    jitter = steady_jitter if steady_jitter is not None else session_jitter
    raw_jitter = steady_raw_jitter if steady_raw_jitter is not None else session_raw_jitter
    jitter_source = "steady_head" if steady_jitter is not None else "session"
    gate = _gate_result(fps, gesture_accuracy, confusion, jitter, args)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "0-poc",
        "privacy": "No video frames are saved; only aggregate metrics and landmark-derived labels are reported.",
        "versions": _versions(),
        "models": {key: asdict(spec) for key, spec in DEFAULT_MODELS.items()},
        "camera": {
            "index": args.camera_index,
            "backend": args.camera_backend,
            "width": args.width,
            "height": args.height,
            "requested_fps": args.camera_fps,
            "face_every_n": args.face_every_n,
            "mirror": args.mirror,
            "active": camera_info,
        },
        "monitors": canvas_to_dict(canvas),
        "metrics": {
            "elapsed_s": elapsed_s,
            "warmup_s": args.warmup_seconds,
            "frames_total": frames,
            "frames_measured": measured_frames,
            "fps_sustained": fps,
            "pipeline_ms_avg": statistics.fmean(processing_ms) if processing_ms else None,
            "pipeline_ms_p95": _percentile(processing_ms, 0.95),
            "head_jitter_filtered_rms_px": jitter,
            "head_jitter_raw_rms_px": raw_jitter,
            "head_frame_delta_filtered_rms_px": (
                frame_delta_rms_px(steady_pointer_samples)
                if steady_jitter is not None
                else frame_delta_rms_px(pointer_samples)
            ),
            "head_samples": len(steady_pointer_samples) if steady_jitter is not None else len(pointer_samples),
            "head_jitter_source": jitter_source,
            "head_jitter_steady_rms_px": steady_jitter,
            "head_jitter_steady_raw_rms_px": steady_raw_jitter,
            "head_frame_delta_steady_rms_px": frame_delta_rms_px(steady_pointer_samples),
            "head_steady_samples": len(steady_pointer_samples),
            "head_jitter_session_rms_px": session_jitter,
            "head_jitter_session_raw_rms_px": session_raw_jitter,
            "head_frame_delta_session_rms_px": frame_delta_rms_px(pointer_samples),
            "head_session_samples": len(pointer_samples),
            "head_jitter_settle_s": args.jitter_settle_seconds,
            "head_jitter_measure_s": args.jitter_seconds,
        },
        "gesture": {
            "samples_per_gesture_target": args.samples_per_gesture,
            "confusion_matrix": confusion,
            "accuracy": gesture_accuracy,
            "progress_pct": _gesture_progress_pct(confusion, args.samples_per_gesture),
            "remaining_samples": _gesture_remaining(confusion, args.samples_per_gesture),
        },
        "gate": gate,
    }


def _gate_result(
    fps: float,
    accuracy: dict[str, float | None],
    confusion: dict[str, dict[str, int]],
    jitter: float | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    fps_pass = fps >= args.fps_gate
    rows_complete = _gate_samples_complete(confusion, args.samples_per_gesture)
    gesture_pass = None
    if rows_complete:
        gesture_pass = all((accuracy[label] or 0.0) >= args.gesture_gate for label in GATE_LABELS)
    jitter_pass = None if jitter is None else jitter <= args.jitter_gate_px
    overall = fps_pass and gesture_pass is True and jitter_pass is True
    return {
        "fps_gate": args.fps_gate,
        "fps_pass": fps_pass,
        "gesture_gate": args.gesture_gate,
        "gesture_rows_complete": rows_complete,
        "gesture_collection_complete": _collection_samples_complete(confusion, args.samples_per_gesture),
        "gesture_pass": gesture_pass,
        "jitter_gate_px": args.jitter_gate_px,
        "jitter_pass": jitter_pass,
        "overall_pass": overall,
    }


def _write_reports(report: dict[str, Any], report_path: Path | None) -> None:
    base = report_path
    if base is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = CAMERA_DATA_DIR / "reports" / f"phase0_camera_{stamp}.json"
    base.parent.mkdir(parents=True, exist_ok=True)
    json_path = base if base.suffix.lower() == ".json" else base.with_suffix(".json")
    md_path = json_path.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")


def _markdown_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    gate = report["gate"]
    lines = [
        "# Camera Control Phase 0 POC Report",
        "",
        f"- Created: {report['created_at']}",
        f"- FPS sustained: {_fmt(metrics['fps_sustained'])}",
        f"- Pipeline avg ms: {_fmt(metrics['pipeline_ms_avg'])}",
        f"- Pipeline p95 ms: {_fmt(metrics['pipeline_ms_p95'])}",
        f"- Head jitter filtered RMS px: {_fmt(metrics['head_jitter_filtered_rms_px'])}",
        f"- Head jitter source: {metrics['head_jitter_source']}",
        f"- Head jitter steady RMS px: {_fmt(metrics['head_jitter_steady_rms_px'])}",
        f"- Head samples: {metrics['head_samples']}",
        f"- Gate overall pass: {gate['overall_pass']}",
        "",
        "## Gesture Accuracy",
        "",
    ]
    for label, value in report["gesture"]["accuracy"].items():
        lines.append(f"- {label}: {_fmt(value)}")
    lines.extend(["", "## Confusion Matrix", "", "```json", json.dumps(report["gesture"]["confusion_matrix"], indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def _versions() -> dict[str, str | None]:
    packages = ("mediapipe", "opencv-python", "opencv-contrib-python", "numpy", "flatbuffers")
    out: dict[str, str | None] = {}
    for package in packages:
        try:
            out[package] = version(package)
        except PackageNotFoundError:
            out[package] = None
    return out


def _empty_confusion() -> dict[str, dict[str, int]]:
    return {label: {pred: 0 for pred in PREDICTION_LABELS} for label in EVAL_LABELS}


def _progress_text(confusion: dict[str, dict[str, int]], target: int, labels: tuple[str, ...]) -> str:
    parts = []
    for label in labels:
        count = _row_total(confusion[label])
        pct = min(100, int(round((count / max(1, target)) * 100)))
        parts.append(f"{label}: {pct:3d}% ({count}/{target})")
    return "progreso: " + " | ".join(parts)


def _gesture_progress_pct(confusion: dict[str, dict[str, int]], target: int) -> dict[str, float]:
    return {
        label: min(100.0, (_row_total(row) / max(1, target)) * 100.0)
        for label, row in confusion.items()
    }


def _gesture_remaining(confusion: dict[str, dict[str, int]], target: int) -> dict[str, int]:
    return {label: max(0, target - _row_total(row)) for label, row in confusion.items()}


def _row_total(row: dict[str, int]) -> int:
    return sum(row.values())


def _gate_samples_complete(confusion: dict[str, dict[str, int]], target: int) -> bool:
    return all(_row_total(confusion[label]) >= target for label in GATE_LABELS)


def _collection_samples_complete(confusion: dict[str, dict[str, int]], target: int) -> bool:
    return all(_row_total(confusion[label]) >= target for label in EVAL_LABELS)


def _gesture_accuracy(confusion: dict[str, dict[str, int]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for label, row in confusion.items():
        total = _row_total(row)
        out[label] = None if total == 0 else row.get(label, 0) / total
    return out


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(math.ceil(q * len(ordered))) - 1
    return ordered[max(0, min(len(ordered) - 1, idx))]


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _camera_label(camera_info: dict[str, Any], requested_backend: str) -> str:
    index = camera_info.get("index", "?")
    backend = camera_info.get("opencv_backend") or requested_backend
    width = camera_info.get("actual_width") or camera_info.get("requested_width") or "?"
    height = camera_info.get("actual_height") or camera_info.get("requested_height") or "?"
    fps = camera_info.get("actual_fps") or camera_info.get("requested_fps") or 0.0
    try:
        fps_text = f"{float(fps):.1f}"
    except (TypeError, ValueError):
        fps_text = "?"
    return f"cam {index} | {backend} | {width}x{height}@{fps_text}"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma 4 camera control Phase 0 POC")
    parser.add_argument("--camera-index", type=int, default=DEFAULT_CAMERA_INDEX)
    parser.add_argument("--camera-backend", choices=("any", "dshow", "msmf"), default=DEFAULT_CAMERA_BACKEND)
    parser.add_argument("--list-cameras", action="store_true")
    parser.add_argument("--camera-scan-limit", type=int, default=8)
    parser.add_argument("--width", type=int, default=DEFAULT_CAMERA_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_CAMERA_HEIGHT)
    parser.add_argument("--camera-fps", type=int, default=30)
    parser.add_argument("--face-every-n", type=int, default=DEFAULT_FACE_EVERY_N)
    parser.add_argument("--iris-refine", dest="iris_refine", action="store_true", default=True)
    parser.add_argument("--no-iris-refine", dest="iris_refine", action="store_false")
    parser.add_argument("--gaze-gain-x", type=float, default=0.62)
    parser.add_argument("--gaze-gain-y", type=float, default=0.42)
    parser.add_argument("--gaze-deadzone", type=float, default=0.025)
    parser.add_argument("--no-auto-center", action="store_true", help="Disable adaptive center for camera placement.")
    parser.add_argument("--auto-center-alpha", type=float, default=0.03)
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run; 0 means until q/esc.")
    parser.add_argument("--warmup-seconds", type=float, default=2.0)
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--mirror", dest="mirror", action="store_true", default=True)
    parser.add_argument("--no-mirror", dest="mirror", action="store_false")
    parser.add_argument("--download-models", action="store_true")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--num-hands", type=int, default=1)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--samples-per-gesture", type=int, default=DEFAULT_SAMPLES_PER_GESTURE)
    parser.add_argument("--jitter-settle-seconds", type=float, default=DEFAULT_JITTER_SETTLE_SECONDS)
    parser.add_argument("--jitter-seconds", type=float, default=DEFAULT_JITTER_SECONDS)
    parser.add_argument("--stabilizer-window", type=int, default=5)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--stop-when-samples-complete", action="store_true")
    parser.add_argument("--fps-gate", type=float, default=20.0)
    parser.add_argument("--gesture-gate", type=float, default=0.95)
    parser.add_argument("--jitter-gate-px", type=float, default=80.0)
    return parser.parse_args(argv)


def list_cameras(args: argparse.Namespace) -> list[dict[str, Any]]:
    import cv2

    backend = _camera_backend_value(args.camera_backend)
    found: list[dict[str, Any]] = []
    for index in range(max(0, int(args.camera_scan_limit))):
        cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
        opened = bool(cap.isOpened())
        item: dict[str, Any] = {
            "index": index,
            "opened": opened,
            "backend": args.camera_backend,
        }
        if opened:
            ok, frame = cap.read()
            item["read_ok"] = bool(ok and frame is not None)
            item["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            item["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            item["fps"] = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            get_backend_name = getattr(cap, "getBackendName", None)
            if get_backend_name is not None:
                try:
                    item["opencv_backend"] = str(get_backend_name())
                except Exception:
                    pass
            if ok and frame is not None:
                item["frame_shape"] = list(frame.shape)
        cap.release()
        if opened:
            found.append(item)
    return found


def _camera_backend_value(name: str) -> int | None:
    if name == "any":
        return None
    import cv2

    if name == "dshow":
        return int(cv2.CAP_DSHOW)
    if name == "msmf":
        return int(cv2.CAP_MSMF)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
