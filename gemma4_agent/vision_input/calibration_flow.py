"""Calibration state machine and validation utilities."""
from __future__ import annotations
import argparse, math, json, os, getpass
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import deque
from pathlib import Path
from typing import Any
import numpy as np
from .calibration import (
    CalibrationProfile, CalibrationSample, CalibrationStore, LinearGazeModel,
    fit_linear_model, fit_monitor_corrections, fit_screen_warp, with_monitor_corrections, with_screen_warp, make_feature_dict
)
from .pointer import HeadPointerEstimate
from .monitors import VirtualCanvas, canvas_to_dict
from .config import KEY_QUIT, KEY_CALIBRATION_CLEAR, KEY_CALIBRATION_NEXT, KEY_CALIBRATION_CAPTURE, KEY_CALIBRATION_SAVE, ONLINE_FEATURE_KEYS

def _head_features(head: HeadPointerEstimate) -> dict[str, float]:
    gaze_x = 0.0
    gaze_y = 0.0
    if head.gaze is not None:
        gaze_x = head.gaze.x
        gaze_y = head.gaze.y
    return make_feature_dict(head.yaw, head.pitch, gaze_x, gaze_y)

def _average_features(buffer: deque[dict[str, float]]) -> dict[str, float]:
    if not buffer:
        return make_feature_dict(0.0, 0.0, 0.0, 0.0)
    keys = ("yaw", "pitch", "gaze_x", "gaze_y")
    return {
        key: sum(float(item.get(key, 0.0)) for item in buffer) / len(buffer)
        for key in keys
    }

def _feature_jitter(samples: tuple[dict[str, float], ...]) -> float:
    if len(samples) < 2:
        return 0.0
    keys = ONLINE_FEATURE_KEYS
    variances: list[float] = []
    for key in keys:
        values = [float(item.get(key, 0.0)) for item in samples]
        mean = sum(values) / len(values)
        variances.append(sum((value - mean) ** 2 for value in values) / len(values))
    return math.sqrt(sum(variances))

@dataclass(frozen=True)
class ValidationSample:
    target_x: float
    target_y: float
    predicted_x: float
    predicted_y: float
    error_px: float
    target_monitor: int
    predicted_monitor: int

    @property
    def monitor_hit(self) -> bool:
        return self.target_monitor == self.predicted_monitor


def _append_online_feature_snapshot(
    history: deque[tuple[float, dict[str, float], tuple[float, float]]],
    *,
    head: HeadPointerEstimate | None,
    desktop_point: tuple[float, float] | None,
    timestamp_s: float,
    min_gaze_confidence: float,
) -> None:
    if head is None or desktop_point is None:
        return
    if not _head_confident_for_online_learn(head, min_gaze_confidence):
        return
    history.append((timestamp_s, _head_features(head), desktop_point))


def _sample_from_click_history(
    *,
    history: deque[tuple[float, dict[str, float], tuple[float, float]]],
    click_xy: tuple[int, int],
    click_timestamp_s: float,
    lag_ms: float,
    window_ms: float,
    max_jitter: float,
    max_click_distance_px: float,
) -> CalibrationSample | None:
    if not history:
        return None
    lag_s = max(0.0, float(lag_ms) / 1000.0)
    win_s = max(0.04, float(window_ms) / 1000.0)
    end_t = click_timestamp_s - lag_s
    start_t = end_t - win_s
    selected = [item for item in history if start_t <= item[0] <= end_t]
    if len(selected) < 3:
        return None
    feature_rows = tuple(item[1] for item in selected)
    jitter = _feature_jitter(feature_rows)
    if jitter > float(max_jitter):
        return None
    features = _average_features(deque(feature_rows))
    avg_x = sum(item[2][0] for item in selected) / len(selected)
    avg_y = sum(item[2][1] for item in selected) / len(selected)
    click_dist = math.hypot(float(click_xy[0]) - avg_x, float(click_xy[1]) - avg_y)
    if click_dist > float(max_click_distance_px):
        return None
    return CalibrationSample(features=features, target_x=float(click_xy[0]), target_y=float(click_xy[1]))


def _handle_validation_keys(
    *,
    key: int,
    hotkeys: list[int],
    desktop_point_buffer: deque[tuple[float, float]],
    target_point: tuple[int, int] | None,
    samples: list[ValidationSample],
    targets: tuple[tuple[int, int], ...],
    target_idx: int,
    canvas: VirtualCanvas,
    min_capture_frames: int,
    args: argparse.Namespace,
) -> tuple[bool, int, bool, dict[str, Any] | None, str]:
    all_keys = _merge_keys(key, hotkeys)
    if any(item in KEY_QUIT for item in all_keys if item >= 0 and item != 255):
        return (False, target_idx, False, None, "")
    effective_key = key
    if effective_key < 0 or effective_key == 255:
        for candidate in all_keys:
            if candidate in KEY_CALIBRATION_CLEAR | KEY_CALIBRATION_NEXT | KEY_CALIBRATION_CAPTURE | KEY_CALIBRATION_SAVE:
                effective_key = candidate
                break
    notice = ""
    if effective_key in KEY_CALIBRATION_CLEAR:
        samples.clear()
        desktop_point_buffer.clear()
        return (True, 0, False, None, "validation samples cleared")
    if effective_key in KEY_CALIBRATION_NEXT and targets:
        desktop_point_buffer.clear()
        return (True, (target_idx + 1) % len(targets), False, None, "next validation target")
    if effective_key in KEY_CALIBRATION_CAPTURE:
        if target_point is None:
            return (True, target_idx, False, None, "validation ignored: no target")
        if len(desktop_point_buffer) < max(1, int(min_capture_frames)):
            return (
                True,
                target_idx,
                False,
                None,
                f"validation waiting: need {max(1, int(min_capture_frames))} gaze frames",
            )
        predicted = _average_points(tuple(desktop_point_buffer))
        sample = _make_validation_sample(canvas, target_point, predicted)
        samples.append(sample)
        desktop_point_buffer.clear()
        next_idx = target_idx + 1
        if next_idx >= len(targets):
            summary = _validation_summary(samples, canvas)
            return (True, max(0, len(targets) - 1), True, summary, "validation complete")
        return (True, next_idx, False, None, f"validated {len(samples)} err={sample.error_px:.0f}px")
    if effective_key in KEY_CALIBRATION_SAVE or key in (10, 13):
        if samples:
            summary = _validation_summary(samples, canvas)
            return (True, target_idx, True, summary, "validation finalized")
        return (True, target_idx, False, None, "need validation samples")
    return (True, target_idx, False, None, notice)


def _average_points(points: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _make_validation_sample(
    canvas: VirtualCanvas,
    target_point: tuple[int, int],
    predicted_point: tuple[float, float],
) -> ValidationSample:
    target_x, target_y = float(target_point[0]), float(target_point[1])
    pred_x, pred_y = float(predicted_point[0]), float(predicted_point[1])
    return ValidationSample(
        target_x=target_x,
        target_y=target_y,
        predicted_x=pred_x,
        predicted_y=pred_y,
        error_px=math.hypot(pred_x - target_x, pred_y - target_y),
        target_monitor=_monitor_index_for_point(canvas, target_x, target_y),
        predicted_monitor=_monitor_index_for_point(canvas, pred_x, pred_y),
    )


def _validation_summary(samples: list[ValidationSample], canvas: VirtualCanvas) -> dict[str, Any] | None:
    if not samples:
        return None
    errors = [sample.error_px for sample in samples]
    hits = [sample.monitor_hit for sample in samples]
    by_monitor: dict[str, dict[str, Any]] = {}
    for monitor in canvas.monitors:
        mon_samples = [sample for sample in samples if sample.target_monitor == monitor.index]
        if not mon_samples:
            continue
        mon_errors = [sample.error_px for sample in mon_samples]
        mon_hits = [sample.monitor_hit for sample in mon_samples]
        by_monitor[str(monitor.index)] = {
            **_error_summary(mon_errors),
            "monitor_accuracy": sum(1 for hit in mon_hits if hit) / len(mon_hits),
        }
    return {
        "sample_count": len(samples),
        "global": _error_summary(errors),
        "monitor_accuracy": sum(1 for hit in hits if hit) / len(hits),
        "by_monitor": by_monitor,
        "samples": [asdict(sample) for sample in samples],
    }


def _validation_summary_passes(summary: dict[str, Any] | None, args: argparse.Namespace) -> bool:
    if summary is None:
        return False
    global_summary = summary.get("global") or {}
    try:
        rms = float(global_summary.get("rms_px"))
        p95 = float(global_summary.get("p95_px"))
        monitor_accuracy = float(summary.get("monitor_accuracy"))
    except (TypeError, ValueError):
        return False
    if rms > float(args.validation_max_rms_px):
        return False
    if p95 > float(args.validation_max_p95_px):
        return False
    if monitor_accuracy < float(args.validation_min_monitor_accuracy):
        return False
    for item in (summary.get("by_monitor") or {}).values():
        try:
            if float(item.get("rms_px")) > float(args.validation_max_rms_px):
                return False
            if float(item.get("p95_px")) > float(args.validation_max_p95_px):
                return False
            if float(item.get("monitor_accuracy")) < float(args.validation_min_monitor_accuracy):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _validation_notice(summary: dict[str, Any] | None, *, passed: bool) -> str:
    if summary is None:
        return "validation failed: no summary"
    global_summary = summary.get("global") or {}
    rms = float(global_summary.get("rms_px") or 0.0)
    p95 = float(global_summary.get("p95_px") or 0.0)
    monitor_accuracy = float(summary.get("monitor_accuracy") or 0.0) * 100.0
    status = "validation PASS" if passed else "validation FAIL: repite puntos malos"
    return f"{status} rms={rms:.0f}px p95={p95:.0f}px monitor={monitor_accuracy:.0f}%"


def _fit_validation_screen_warp(
    model: LinearGazeModel,
    samples: list[ValidationSample],
    canvas: VirtualCanvas,
    *,
    max_rms_px: float,
) -> tuple[LinearGazeModel | None, dict[str, Any] | None]:
    if len(samples) < 6:
        return (None, None)
    warp = fit_screen_warp(
        tuple((sample.predicted_x, sample.predicted_y, sample.target_x, sample.target_y) for sample in samples),
        degree=2,
    )
    if warp is None or warp.rms_error_px > float(max_rms_px):
        return (None, None)
    warped_model = with_screen_warp(model, warp)
    corrected_samples = [
        _make_validation_sample(
            canvas,
            (int(round(sample.target_x)), int(round(sample.target_y))),
            warp.apply(sample.predicted_x, sample.predicted_y),
        )
        for sample in samples
    ]
    return (warped_model, _validation_summary(corrected_samples, canvas))


def _bad_validation_targets(
    samples: list[ValidationSample],
    max_point_error_px: float,
    repeat_worst: int,
) -> tuple[tuple[int, int], ...]:
    if not samples:
        return tuple()
    bad = [
        sample
        for sample in samples
        if sample.error_px >= float(max_point_error_px) or not sample.monitor_hit
    ]
    if not bad:
        bad = sorted(samples, key=lambda sample: sample.error_px, reverse=True)[: max(1, int(repeat_worst))]
    else:
        bad = sorted(bad, key=lambda sample: (not sample.monitor_hit, sample.error_px), reverse=True)
    out: list[tuple[int, int]] = []
    for sample in bad[: max(1, int(repeat_worst))]:
        target = (int(round(sample.target_x)), int(round(sample.target_y)))
        if target not in out:
            out.append(target)
    return tuple(out)


def _monitor_index_for_point(canvas: VirtualCanvas, x: float, y: float) -> int:
    containing = [
        monitor
        for monitor in canvas.monitors
        if monitor.rect.left <= x < monitor.rect.right and monitor.rect.top <= y < monitor.rect.bottom
    ]
    if containing:
        return containing[0].index
    nearest = min(
        canvas.monitors,
        key=lambda monitor: (monitor.rect.center[0] - x) ** 2 + (monitor.rect.center[1] - y) ** 2,
    )
    return nearest.index


def _error_summary(errors: list[float]) -> dict[str, Any]:
    if not errors:
        return {"count": 0, "rms_px": None, "mean_px": None, "p95_px": None, "max_px": None}
    arr = np.asarray(errors, dtype=float)
    return {
        "count": int(arr.size),
        "rms_px": float(np.sqrt(np.mean(arr * arr))),
        "mean_px": float(np.mean(arr)),
        "p95_px": float(np.percentile(arr, 95)),
        "max_px": float(np.max(arr)),
    }


def _handle_calibration_keys(
    *,
    key: int,
    hotkeys: list[int],
    head: HeadPointerEstimate | None,
    target_point: tuple[int, int] | None,
    samples: list[CalibrationSample],
    feature_buffer: deque[dict[str, float]],
    targets: tuple[tuple[int, int], ...],
    target_idx: int,
    min_samples: int,
    layout_hash: str,
    canvas: VirtualCanvas,
    camera_resolution: tuple[int, int] | None,
    store: CalibrationStore,
    user: str | None,
    merge_with_existing: bool,
    max_history_samples: int,
    max_merge_rms_px: float,
    min_capture_frames: int,
    max_capture_feature_jitter: float,
    min_capture_gaze_confidence: float,
) -> tuple[bool, int, LinearGazeModel | None, Path | None, str]:
    all_keys = _merge_keys(key, hotkeys)
    if any(item in KEY_QUIT for item in all_keys if item >= 0 and item != 255):
        return (False, target_idx, None, None, "")
    effective_key = key
    if effective_key < 0 or effective_key == 255:
        for candidate in all_keys:
            if candidate in KEY_CALIBRATION_CLEAR | KEY_CALIBRATION_NEXT | KEY_CALIBRATION_CAPTURE | KEY_CALIBRATION_SAVE:
                effective_key = candidate
                break
    saved_path = None
    model = None
    notice = ""
    if effective_key in KEY_CALIBRATION_CLEAR:
        samples.clear()
        feature_buffer.clear()
        notice = "samples cleared"
    elif effective_key in KEY_CALIBRATION_NEXT and targets:
        target_idx = (target_idx + 1) % len(targets)
        notice = "next target"
    elif effective_key in KEY_CALIBRATION_CAPTURE:
        if target_point is None:
            notice = "capture ignored: no target"
            return (True, target_idx, model, saved_path, notice)
        if head is None:
            notice = "capture rejected: no face/head detected"
            return (True, target_idx, model, saved_path, notice)
        if len(feature_buffer) < max(1, int(min_capture_frames)):
            notice = f"hold still: need {max(1, int(min_capture_frames))} stable frames"
            return (True, target_idx, model, saved_path, notice)
        if not _head_confident_for_online_learn(head, min_capture_gaze_confidence):
            notice = "capture rejected: low gaze confidence"
            return (True, target_idx, model, saved_path, notice)
        jitter = _feature_jitter(tuple(feature_buffer))
        if jitter > float(max_capture_feature_jitter):
            notice = f"capture rejected: unstable ({jitter:.3f})"
            return (True, target_idx, model, saved_path, notice)
        features = _average_features(feature_buffer) if feature_buffer else _head_features(head)
        samples.append(CalibrationSample(features=features, target_x=float(target_point[0]), target_y=float(target_point[1])))
        feature_buffer.clear()
        if targets:
            target_idx = (target_idx + 1) % len(targets)
        notice = f"captured {len(samples)}"
    elif effective_key in KEY_CALIBRATION_SAVE or key in (10, 13):
        if len(samples) >= max(6, int(min_samples)):
            current_samples = tuple(samples)
            current_model = fit_linear_model(current_samples)
            training_samples = current_samples
            model = current_model
            previous_count = 0
            merge_attempted = False
            if merge_with_existing:
                previous = store.load(layout_hash, user)
                if previous is not None and previous.samples:
                    previous_count = len(previous.samples)
                    merge_attempted = True
                    merged_samples = _merge_calibration_samples(
                        previous.samples,
                        current_samples,
                        max_samples=max_history_samples,
                    )
                    merged_model = fit_linear_model(merged_samples)
                    if (
                        merged_model is not None
                        and (model is None or merged_model.rms_error_px <= model.rms_error_px)
                    ):
                        model = merged_model
                        training_samples = merged_samples
            if model is not None:
                if model.rms_error_px > float(max_merge_rms_px):
                    return (
                        True,
                        target_idx,
                        None,
                        None,
                        f"save rejected: rms {model.rms_error_px:.1f}px > {max_merge_rms_px:.1f}px",
                    )
                # Per-monitor local correction: each monitor gets its own
                # predicted->target warp from its own samples, so a weak-signal
                # monitor (e.g. one placed below) stops smearing the others. Only
                # corrections that improve their monitor's RMS are kept.
                corrections = fit_monitor_corrections(model, training_samples, canvas)
                if corrections:
                    model = with_monitor_corrections(model, corrections)
                profile = CalibrationProfile(
                    user=user or getpass.getuser() or "default",
                    layout_hash=layout_hash,
                    samples=training_samples,
                    rms_error_px=model.rms_error_px,
                    model=model.to_dict(),
                    camera_resolution=camera_resolution,
                )
                saved_path = store.save(profile)
                if merge_attempted and len(training_samples) > len(current_samples):
                    merge_text = f"merged {previous_count}+{len(current_samples)} -> {len(training_samples)}"
                elif merge_attempted:
                    merge_text = f"merge skipped (current better) {len(current_samples)}"
                else:
                    merge_text = f"saved current {len(current_samples)}"
                return (False, target_idx, model, saved_path, f"{merge_text} | rms {model.rms_error_px:.1f}px")
            notice = "save failed: model fit returned none"
        else:
            notice = f"need >= {max(6, int(min_samples))} samples"
    return (True, target_idx, model, saved_path, notice)


def _set_cursor_pos(point: tuple[int, int]) -> None:
    if win32api is None:
        return
    try:
        win32api.SetCursorPos((int(point[0]), int(point[1])))
    except Exception:
        pass


def _has_capture_key(keys: list[int]) -> bool:
    return any(key in KEY_CALIBRATION_CAPTURE for key in keys if key >= 0 and key != 255)


def _merge_keys(primary_key: int, hotkeys: list[int]) -> list[int]:
    merged: list[int] = []
    if primary_key >= 0 and primary_key != 255:
        merged.append(primary_key)
    for key in hotkeys:
        if key >= 0 and key != 255 and key not in merged:
            merged.append(key)
    return merged


def _merge_calibration_samples(
    previous: tuple[CalibrationSample, ...],
    current: tuple[CalibrationSample, ...],
    *,
    max_samples: int,
) -> tuple[CalibrationSample, ...]:
    limit = max(1, int(max_samples))
    merged = tuple(previous) + tuple(current)
    if len(merged) <= limit:
        return merged
    return merged[-limit:]


def _head_confident_for_online_learn(head: HeadPointerEstimate, min_confidence: float) -> bool:
    if head.gaze is None:
        return False
    confidence = float(getattr(head.gaze, "confidence", 0.0))
    return math.isfinite(confidence) and confidence >= float(min_confidence)


def _save_calibration_profile(
    *,
    store: CalibrationStore,
    layout_hash: str,
    user: str | None,
    samples: tuple[CalibrationSample, ...],
    model: LinearGazeModel,
) -> Path:
    profile = CalibrationProfile(
        user=user or getpass.getuser() or "default",
        layout_hash=layout_hash,
        samples=samples,
        rms_error_px=model.rms_error_px,
        model=model.to_dict(),
    )
    return store.save(profile)


def _save_calibration_debug_capture(
    *,
    frame: Any,
    output_dir: Path,
    index: int,
    mode: str,
    notice: str,
    target_point: tuple[int, int] | None,
    desktop_point: tuple[float, float] | None,
    head: HeadPointerEstimate | None,
    canvas: VirtualCanvas,
    sample_count_before: int,
    sample_count_after: int,
    validation_sample: ValidationSample | None,
) -> tuple[Path, Path] | None:
    import cv2

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = f"{index:04d}_{stamp}_{mode}"
    png_path = output_dir / f"{stem}.png"
    json_path = output_dir / f"{stem}.json"
    try:
        cv2.imwrite(str(png_path), frame)
    except Exception:
        return None
    target_monitor = None
    if target_point is not None:
        target_monitor = _monitor_index_for_point(canvas, float(target_point[0]), float(target_point[1]))
    predicted_monitor = None
    if desktop_point is not None:
        predicted_monitor = _monitor_index_for_point(canvas, float(desktop_point[0]), float(desktop_point[1]))
    payload = {
        "created_at": datetime.now().isoformat(timespec="milliseconds"),
        "mode": mode,
        "notice": notice,
        "image_path": str(png_path),
        "target_point": list(target_point) if target_point is not None else None,
        "target_monitor": target_monitor,
        "predicted_point": list(desktop_point) if desktop_point is not None else None,
        "predicted_monitor": predicted_monitor,
        "sample_count_before": sample_count_before,
        "sample_count_after": sample_count_after,
        "sample_saved": sample_count_after > sample_count_before,
        "head": _head_debug_payload(head),
        "validation_sample": asdict(validation_sample) if validation_sample is not None else None,
        "canvas": canvas_to_dict(canvas),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return (png_path, json_path)


def _head_debug_payload(head: HeadPointerEstimate | None) -> dict[str, Any] | None:
    if head is None:
        return None
    gaze = None
    if head.gaze is not None:
        gaze = {
            "x": head.gaze.x,
            "y": head.gaze.y,
            "confidence": head.gaze.confidence,
            "left_x": head.gaze.left_x,
            "left_y": head.gaze.left_y,
            "right_x": head.gaze.right_x,
            "right_y": head.gaze.right_y,
        }
    return {
        "yaw": head.yaw,
        "pitch": head.pitch,
        "raw_x": head.raw_x,
        "raw_y": head.raw_y,
        "filtered_x": head.filtered_x,
        "filtered_y": head.filtered_y,
        "monitor_index": head.monitor.index,
        "monitor_device": head.monitor.device,
        "region": head.region,
        "source": head.source,
        "local_x": head.local_x,
        "local_y": head.local_y,
        "features": _head_features(head),
        "gaze": gaze,
    }


def _online_retrain_from_clicks(
    *,
    store: CalibrationStore,
    layout_hash: str,
    user: str | None,
    loaded_model: LinearGazeModel | None,
    active_model: LinearGazeModel | None,
    recent_samples: tuple[CalibrationSample, ...],
    max_total_samples: int,
    max_rms_px: float,
) -> tuple[LinearGazeModel | None, LinearGazeModel | None, bool]:
    if len(recent_samples) < 6:
        return active_model, loaded_model, False
    previous = store.load(layout_hash, user)
    previous_samples = previous.samples if previous is not None else ()
    merged_samples = _merge_calibration_samples(previous_samples, recent_samples, max_samples=max_total_samples)
    model = fit_linear_model(merged_samples, feature_keys=ONLINE_FEATURE_KEYS, robust_trim_quantile=0.78, robust_passes=3)
    if model is None:
        return active_model, loaded_model, False
    if model.rms_error_px > float(max_rms_px):
        return active_model, loaded_model, False
    baseline_rms = loaded_model.rms_error_px if loaded_model is not None else float("inf")
    if active_model is not None:
        baseline_rms = min(baseline_rms, active_model.rms_error_px)
    if math.isfinite(baseline_rms) and model.rms_error_px > baseline_rms * 1.05:
        return active_model, loaded_model, False
    profile = CalibrationProfile(
        user=user or getpass.getuser() or "default",
        layout_hash=layout_hash,
        samples=merged_samples,
        rms_error_px=model.rms_error_px,
        model=model.to_dict(),
    )
    store.save(profile)
    return model, model, True


