"""Local calibration persistence for later camera-control phases."""
from __future__ import annotations

import getpass
import json
import os
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .landmarks import CAMERA_DATA_DIR
from .monitors import VirtualCanvas


@dataclass(frozen=True)
class CalibrationSample:
    features: dict[str, float]
    target_x: float
    target_y: float


@dataclass(frozen=True)
class CalibrationProfile:
    user: str
    layout_hash: str
    samples: tuple[CalibrationSample, ...]
    rms_error_px: float | None = None
    version: int = 2
    model: dict[str, Any] | None = None
    # Camera resolution the calibration was captured at. Landmark detail/noise
    # depends on it, so running at a different resolution silently degrades the
    # learned mapping. Stored so the runtime can warn on a mismatch instead of
    # quietly losing accuracy. (width, height) or None for legacy profiles.
    camera_resolution: tuple[int, int] | None = None


@dataclass(frozen=True)
class ScreenWarpModel:
    coeffs_x: tuple[float, ...]
    coeffs_y: tuple[float, ...]
    center_x: float
    center_y: float
    scale_x: float
    scale_y: float
    rms_error_px: float
    degree: int = 2

    def apply(self, x: float, y: float) -> tuple[float, float]:
        vec = _screen_design_row(x, y, self)
        out_x = float(np.dot(np.asarray(self.coeffs_x, dtype=float), vec))
        out_y = float(np.dot(np.asarray(self.coeffs_y, dtype=float), vec))
        return (out_x, out_y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "screen-warp-v1",
            "coeffs_x": list(self.coeffs_x),
            "coeffs_y": list(self.coeffs_y),
            "center_x": self.center_x,
            "center_y": self.center_y,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "rms_error_px": self.rms_error_px,
            "degree": self.degree,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ScreenWarpModel | None:
        if not isinstance(data, dict) or str(data.get("type") or "") != "screen-warp-v1":
            return None
        try:
            degree = int(data.get("degree") or 2)
            coeffs_x = tuple(float(item) for item in data.get("coeffs_x") or [])
            coeffs_y = tuple(float(item) for item in data.get("coeffs_y") or [])
            center_x = float(data.get("center_x"))
            center_y = float(data.get("center_y"))
            scale_x = float(data.get("scale_x"))
            scale_y = float(data.get("scale_y"))
            rms_error_px = float(data.get("rms_error_px") or 0.0)
        except (TypeError, ValueError):
            return None
        expected = _screen_design_col_count(degree)
        if len(coeffs_x) != expected or len(coeffs_y) != expected:
            return None
        values = (*coeffs_x, *coeffs_y, center_x, center_y, scale_x, scale_y, rms_error_px)
        if not all(math.isfinite(item) for item in values):
            return None
        if scale_x <= 0.0 or scale_y <= 0.0:
            return None
        return cls(
            coeffs_x=coeffs_x,
            coeffs_y=coeffs_y,
            center_x=center_x,
            center_y=center_y,
            scale_x=scale_x,
            scale_y=scale_y,
            rms_error_px=rms_error_px,
            degree=max(1, min(2, degree)),
        )


@dataclass(frozen=True)
class MonitorCorrection:
    """Per-monitor local correction applied after the global model.

    A single global polynomial must serve every monitor at once; on a layout with
    a monitor BELOW the others (weak head-pitch signal) it becomes a compromise
    that smears all of them. Each monitor instead gets its own predicted->target
    warp, fit only from that monitor's samples, routed by the globally-predicted
    point's location. Measured motivation: bottom-monitor RMS 277px under the
    global-only model while the coplanar monitors sat near ~100px.
    """

    left: int
    top: int
    right: int
    bottom: int
    warp: ScreenWarpModel

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    @property
    def center(self) -> tuple[float, float]:
        return ((self.left + self.right) / 2.0, (self.top + self.bottom) / 2.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "warp": self.warp.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MonitorCorrection | None:
        if not isinstance(data, dict):
            return None
        warp = ScreenWarpModel.from_dict(data.get("warp"))
        if warp is None:
            return None
        try:
            return cls(
                left=int(data["left"]),
                top=int(data["top"]),
                right=int(data["right"]),
                bottom=int(data["bottom"]),
                warp=warp,
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class LinearGazeModel:
    feature_keys: tuple[str, ...]
    coeffs_x: tuple[float, ...]
    coeffs_y: tuple[float, ...]
    rms_error_px: float
    degree: int = 1
    screen_warp: ScreenWarpModel | None = None
    monitor_corrections: tuple[MonitorCorrection, ...] = ()

    def predict(self, features: dict[str, float]) -> tuple[float, float]:
        vec = _design_row(features, self.feature_keys, self.degree)
        x = float(np.dot(np.asarray(self.coeffs_x, dtype=float), vec))
        y = float(np.dot(np.asarray(self.coeffs_y, dtype=float), vec))
        if self.screen_warp is not None:
            x, y = self.screen_warp.apply(x, y)
        x, y = self._apply_monitor_correction(x, y)
        return (x, y)

    def _apply_monitor_correction(self, x: float, y: float) -> tuple[float, float]:
        if not self.monitor_corrections:
            return (x, y)
        # Route by the globally-predicted point: the monitor it lands in, else the
        # nearest monitor center (so points in a gap still get the closest fit).
        chosen = next((mc for mc in self.monitor_corrections if mc.contains(x, y)), None)
        if chosen is None:
            chosen = min(
                self.monitor_corrections,
                key=lambda mc: (mc.center[0] - x) ** 2 + (mc.center[1] - y) ** 2,
            )
        return chosen.warp.apply(x, y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "linear-v1",
            "feature_keys": list(self.feature_keys),
            "coeffs_x": list(self.coeffs_x),
            "coeffs_y": list(self.coeffs_y),
            "rms_error_px": self.rms_error_px,
            "degree": self.degree,
            "screen_warp": self.screen_warp.to_dict() if self.screen_warp is not None else None,
            "monitor_corrections": [mc.to_dict() for mc in self.monitor_corrections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LinearGazeModel | None:
        if str(data.get("type") or "") != "linear-v1":
            return None
        feature_keys = tuple(str(item) for item in data.get("feature_keys") or [])
        try:
            coeffs_x = tuple(float(item) for item in data.get("coeffs_x") or [])
            coeffs_y = tuple(float(item) for item in data.get("coeffs_y") or [])
        except (TypeError, ValueError):
            return None
        if not feature_keys:
            return None
        degree = int(data.get("degree") or 1)
        expected = _design_col_count(len(feature_keys), degree)
        if len(coeffs_x) != expected or len(coeffs_y) != expected:
            return None
        if not all(math.isfinite(item) for item in (*coeffs_x, *coeffs_y)):
            return None
        try:
            rms_error_px = float(data.get("rms_error_px") or 0.0)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(rms_error_px):
            return None
        screen_warp = ScreenWarpModel.from_dict(data.get("screen_warp"))
        corrections = tuple(
            mc for mc in (MonitorCorrection.from_dict(item) for item in (data.get("monitor_corrections") or []))
            if mc is not None
        )
        return cls(
            feature_keys=feature_keys,
            coeffs_x=coeffs_x,
            coeffs_y=coeffs_y,
            rms_error_px=rms_error_px,
            degree=degree,
            screen_warp=screen_warp,
            monitor_corrections=corrections,
        )


class CalibrationStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or CAMERA_DATA_DIR

    def path_for(self, layout_hash: str, user: str | None = None) -> Path:
        safe_user = _safe_name(user or getpass.getuser() or "default")
        return self.base_dir / safe_user / f"calib_{layout_hash}.json"

    def load(self, layout_hash: str, user: str | None = None) -> CalibrationProfile | None:
        path = self.path_for(layout_hash, user)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            samples = tuple(CalibrationSample(**item) for item in data.get("samples", []))
            res = data.get("camera_resolution")
            camera_resolution = None
            if isinstance(res, (list, tuple)) and len(res) == 2:
                try:
                    camera_resolution = (int(res[0]), int(res[1]))
                except (TypeError, ValueError):
                    camera_resolution = None
            return CalibrationProfile(
                user=str(data.get("user") or user or "default"),
                layout_hash=str(data.get("layout_hash") or layout_hash),
                samples=samples,
                rms_error_px=data.get("rms_error_px"),
                version=int(data.get("version") or 1),
                model=data.get("model"),
                camera_resolution=camera_resolution,
            )
        except (OSError, ValueError, TypeError):
            return None

    def save(self, profile: CalibrationProfile) -> Path:
        path = self.path_for(profile.layout_hash, profile.user)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "user": profile.user,
            "layout_hash": profile.layout_hash,
            "samples": [asdict(sample) for sample in profile.samples],
            "rms_error_px": profile.rms_error_px,
            "version": profile.version,
            "model": profile.model,
            "camera_resolution": list(profile.camera_resolution) if profile.camera_resolution else None,
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
        return path


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)[:80] or "default"


DEFAULT_FEATURE_KEYS = ("yaw", "pitch", "gaze_x", "gaze_y")


def make_feature_dict(yaw: float, pitch: float, gaze_x: float, gaze_y: float) -> dict[str, float]:
    return {
        "yaw": _safe_float(yaw),
        "pitch": _safe_float(pitch),
        "gaze_x": _safe_float(gaze_x),
        "gaze_y": _safe_float(gaze_y),
    }


def fit_linear_model(
    samples: Sequence[CalibrationSample],
    feature_keys: Sequence[str] = DEFAULT_FEATURE_KEYS,
    ridge: float = 1e-3,
    degree: int = 2,
    edge_weight_gain: float = 1.5,
    robust_trim_quantile: float = 0.84,
    robust_passes: int = 2,
) -> LinearGazeModel | None:
    keys = tuple(str(item) for item in feature_keys)
    if len(samples) < max(6, len(keys) + 2):
        return None
    clean_samples: list[CalibrationSample] = []
    for sample in samples:
        feats = [_safe_float(sample.features.get(key, 0.0)) for key in keys]
        tx = _safe_float(sample.target_x)
        ty = _safe_float(sample.target_y)
        if not all(math.isfinite(item) for item in (*feats, tx, ty)):
            continue
        clean_samples.append(CalibrationSample(features={key: feats[idx] for idx, key in enumerate(keys)}, target_x=tx, target_y=ty))
    if len(clean_samples) < max(6, len(keys) + 2):
        return None
    best = _fit_core_model(clean_samples, keys, degree=degree, ridge=ridge, edge_weight_gain=edge_weight_gain)
    linear = _fit_core_model(clean_samples, keys, degree=1, ridge=ridge, edge_weight_gain=edge_weight_gain)
    if best is None:
        best = linear
    elif linear is not None and linear.rms_error_px < best.rms_error_px:
        best = linear
    if best is None:
        return None

    if len(clean_samples) >= max(12, len(keys) * 3):
        work = tuple(clean_samples)
        trim_q = max(0.55, min(0.95, float(robust_trim_quantile)))
        passes = max(0, int(robust_passes))
        for _ in range(passes):
            residuals = _residuals_px(best, work)
            if len(residuals) < max(10, len(keys) + 4):
                break
            threshold = float(np.quantile(np.asarray(residuals, dtype=float), trim_q))
            kept = tuple(sample for sample, err in zip(work, residuals) if err <= threshold)
            if len(kept) < max(8, len(keys) + 2) or len(kept) >= len(work):
                break
            candidate = _fit_core_model(kept, keys, degree=best.degree, ridge=ridge, edge_weight_gain=edge_weight_gain)
            if candidate is None:
                break
            work = kept
            # Keep candidate only if it also improves on full clean set.
            full_rms = _rms_on_samples(candidate, clean_samples)
            if full_rms <= best.rms_error_px:
                best = LinearGazeModel(
                    feature_keys=candidate.feature_keys,
                    coeffs_x=candidate.coeffs_x,
                    coeffs_y=candidate.coeffs_y,
                    rms_error_px=full_rms,
                    degree=candidate.degree,
                )
    return best


def leave_one_out_rms(
    samples: Sequence[CalibrationSample],
    feature_keys: Sequence[str] = DEFAULT_FEATURE_KEYS,
    *,
    ridge: float = 1e-3,
    degree: int = 2,
) -> float | None:
    """Held-out RMS (px) via leave-one-out cross-validation.

    The model's own ``rms_error_px`` is the residual on the SAME points it was
    fit on, so it is optimistic (overfit-blind) — a degree-2 fit on 9 points can
    look great and generalize poorly. LOO-CV refits leaving each sample out and
    measures error on that held-out sample, giving an honest estimate to GATE on.
    Returns None if there are too few samples to leave one out.
    """
    keys = tuple(str(k) for k in feature_keys)
    items = list(samples)
    min_needed = max(6, len(keys) + 2) + 1
    if len(items) < min_needed:
        return None
    squared: list[float] = []
    for held in range(len(items)):
        train = items[:held] + items[held + 1:]
        model = fit_linear_model(train, keys, ridge=ridge, degree=degree)
        if model is None:
            return None
        px, py = model.predict(items[held].features)
        tx, ty = items[held].target_x, items[held].target_y
        if not all(math.isfinite(v) for v in (px, py, tx, ty)):
            return None
        squared.append((px - tx) ** 2 + (py - ty) ** 2)
    if not squared:
        return None
    return float(math.sqrt(sum(squared) / len(squared)))


def select_ridge_by_loo(
    samples: Sequence[CalibrationSample],
    feature_keys: Sequence[str] = DEFAULT_FEATURE_KEYS,
    *,
    candidates: Sequence[float] = (1e-3, 3e-3, 1e-2, 3e-2, 1e-1),
    degree: int = 2,
) -> tuple[float, float] | None:
    """Pick the ridge that minimizes held-out (LOO-CV) error.

    Returns (best_ridge, loo_rms_px). The literature on webcam gaze calibration
    (PMC10966887) found ~1e-2 robust, an order of magnitude above the current
    1e-3 default; rather than hardcode that on synthetic data, select per-session
    by held-out error. Falls back to None if LOO is not computable.
    """
    best: tuple[float, float] | None = None
    for ridge in candidates:
        loo = leave_one_out_rms(samples, feature_keys, ridge=float(ridge), degree=degree)
        if loo is None:
            continue
        if best is None or loo < best[1]:
            best = (float(ridge), loo)
    return best


def with_screen_warp(model: LinearGazeModel, warp: ScreenWarpModel | None) -> LinearGazeModel:
    return LinearGazeModel(
        feature_keys=model.feature_keys,
        coeffs_x=model.coeffs_x,
        coeffs_y=model.coeffs_y,
        rms_error_px=model.rms_error_px,
        degree=model.degree,
        screen_warp=warp,
        monitor_corrections=model.monitor_corrections,
    )


def with_monitor_corrections(
    model: LinearGazeModel,
    corrections: tuple[MonitorCorrection, ...],
) -> LinearGazeModel:
    return LinearGazeModel(
        feature_keys=model.feature_keys,
        coeffs_x=model.coeffs_x,
        coeffs_y=model.coeffs_y,
        rms_error_px=model.rms_error_px,
        degree=model.degree,
        screen_warp=model.screen_warp,
        monitor_corrections=corrections,
    )


def fit_monitor_corrections(
    model: LinearGazeModel,
    samples: Sequence[CalibrationSample],
    canvas: VirtualCanvas,
    *,
    min_samples_per_monitor: int = 4,
    ridge: float = 1e-3,
) -> tuple[MonitorCorrection, ...]:
    """Fit one local predicted->target warp per monitor from its own samples.

    Each monitor's correction is fit ONLY on samples whose target lands on it, so
    a weak-signal monitor (e.g. one placed below) can't smear the others. A
    monitor is corrected only if (a) it has enough samples and (b) the correction
    does not make that monitor's own RMS worse (guard against overfit on few
    points). Returns the corrections that earned their place; routing is by the
    globally-predicted point inside LinearGazeModel.predict.
    """
    if model is None or not samples:
        return ()
    by_monitor: dict[int, list[CalibrationSample]] = {}
    for sample in samples:
        idx = _monitor_index_for_point(canvas, sample.target_x, sample.target_y)
        by_monitor.setdefault(idx, []).append(sample)

    out: list[MonitorCorrection] = []
    for monitor in canvas.monitors:
        mon_samples = by_monitor.get(monitor.index, [])
        if len(mon_samples) < max(3, int(min_samples_per_monitor)):
            continue
        rows: list[tuple[float, float, float, float]] = []
        base_sq = 0.0
        for sample in mon_samples:
            px, py = model.predict(sample.features)
            if not all(math.isfinite(v) for v in (px, py, sample.target_x, sample.target_y)):
                continue
            rows.append((px, py, sample.target_x, sample.target_y))
            base_sq += (px - sample.target_x) ** 2 + (py - sample.target_y) ** 2
        if len(rows) < max(3, int(min_samples_per_monitor)):
            continue
        warp = fit_screen_warp(rows, ridge=ridge)
        if warp is None:
            continue
        # Only keep it if it improves THIS monitor's RMS over the global model.
        base_rms = math.sqrt(base_sq / len(rows)) if rows else float("inf")
        corr_sq = 0.0
        for px, py, tx, ty in rows:
            cx, cy = warp.apply(px, py)
            corr_sq += (cx - tx) ** 2 + (cy - ty) ** 2
        corr_rms = math.sqrt(corr_sq / len(rows))
        if corr_rms > base_rms:
            continue
        out.append(
            MonitorCorrection(
                left=monitor.rect.left,
                top=monitor.rect.top,
                right=monitor.rect.right,
                bottom=monitor.rect.bottom,
                warp=warp,
            )
        )
    return tuple(out)


def fit_screen_warp(
    samples: Sequence[tuple[float, float, float, float]],
    *,
    degree: int = 2,
    ridge: float = 1e-3,
) -> ScreenWarpModel | None:
    """Fit a deterministic screen-space correction from predicted to target points."""
    rows: list[tuple[float, float, float, float]] = []
    for pred_x, pred_y, target_x, target_y in samples:
        values = tuple(_safe_float(item) for item in (pred_x, pred_y, target_x, target_y))
        if all(math.isfinite(item) for item in values):
            rows.append(values)
    if len(rows) < 3:
        return None
    wanted_degree = 2 if int(degree) >= 2 and len(rows) >= 6 else 1
    pred_xs = np.asarray([row[0] for row in rows], dtype=float)
    pred_ys = np.asarray([row[1] for row in rows], dtype=float)
    center_x = float((np.min(pred_xs) + np.max(pred_xs)) / 2.0)
    center_y = float((np.min(pred_ys) + np.max(pred_ys)) / 2.0)
    scale_x = float(max(1.0, (np.max(pred_xs) - np.min(pred_xs)) / 2.0))
    scale_y = float(max(1.0, (np.max(pred_ys) - np.min(pred_ys)) / 2.0))
    template = ScreenWarpModel(
        coeffs_x=tuple(0.0 for _ in range(_screen_design_col_count(wanted_degree))),
        coeffs_y=tuple(0.0 for _ in range(_screen_design_col_count(wanted_degree))),
        center_x=center_x,
        center_y=center_y,
        scale_x=scale_x,
        scale_y=scale_y,
        rms_error_px=float("inf"),
        degree=wanted_degree,
    )
    x_mat = np.asarray([_screen_design_row(row[0], row[1], template) for row in rows], dtype=float)
    target_x = np.asarray([row[2] for row in rows], dtype=float)
    target_y = np.asarray([row[3] for row in rows], dtype=float)
    cols = x_mat.shape[1]
    eye = np.eye(cols, dtype=float)
    eye[0, 0] = 0.0
    xtx = x_mat.T @ x_mat + max(0.0, float(ridge)) * eye
    try:
        inv = np.linalg.pinv(xtx)
    except np.linalg.LinAlgError:
        return None
    coeffs_x = inv @ x_mat.T @ target_x
    coeffs_y = inv @ x_mat.T @ target_y
    out_x = x_mat @ coeffs_x
    out_y = x_mat @ coeffs_y
    rms_error = float(np.sqrt(np.mean((out_x - target_x) ** 2 + (out_y - target_y) ** 2)))
    if not math.isfinite(rms_error):
        return None
    return ScreenWarpModel(
        coeffs_x=tuple(float(item) for item in coeffs_x.tolist()),
        coeffs_y=tuple(float(item) for item in coeffs_y.tolist()),
        center_x=center_x,
        center_y=center_y,
        scale_x=scale_x,
        scale_y=scale_y,
        rms_error_px=rms_error,
        degree=wanted_degree,
    )


def profile_model(profile: CalibrationProfile | None) -> LinearGazeModel | None:
    if profile is None or not isinstance(profile.model, dict):
        return None
    return LinearGazeModel.from_dict(profile.model)


def default_calibration_targets(canvas: VirtualCanvas, margin: float = 0.12) -> tuple[tuple[int, int], ...]:
    pts: list[tuple[int, int]] = []
    m = max(0.02, min(0.45, margin))
    for monitor in sorted(canvas.monitors, key=lambda item: (item.rect.left, item.rect.top, item.index)):
        left = monitor.rect.left
        top = monitor.rect.top
        width = max(1, monitor.rect.width)
        height = max(1, monitor.rect.height)
        for nx, ny in ((0.5, 0.5), (m, m), (1.0 - m, m), (m, 1.0 - m), (1.0 - m, 1.0 - m)):
            pts.append((int(round(left + nx * width)), int(round(top + ny * height))))
    return tuple(pts)


def evaluate_calibration_model(
    model: LinearGazeModel | None,
    samples: Sequence[CalibrationSample],
    canvas: VirtualCanvas,
) -> dict[str, Any] | None:
    """Return global and per-monitor calibration errors in desktop pixels."""
    if model is None or not samples:
        return None
    rows: list[tuple[int, float]] = []
    for sample in samples:
        try:
            px, py = model.predict(sample.features)
        except Exception:
            continue
        if not all(math.isfinite(item) for item in (px, py, sample.target_x, sample.target_y)):
            continue
        monitor_index = _monitor_index_for_point(canvas, sample.target_x, sample.target_y)
        rows.append((monitor_index, math.hypot(px - sample.target_x, py - sample.target_y)))
    if not rows:
        return None
    all_errors = [err for _, err in rows]
    by_monitor: dict[str, dict[str, Any]] = {}
    for monitor in canvas.monitors:
        errors = [err for idx, err in rows if idx == monitor.index]
        if not errors:
            continue
        by_monitor[str(monitor.index)] = _error_summary(errors)
    return {
        "sample_count": len(rows),
        "global": _error_summary(all_errors),
        "by_monitor": by_monitor,
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return out


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


def _error_summary(errors: Sequence[float]) -> dict[str, Any]:
    arr = np.asarray([float(err) for err in errors], dtype=float)
    return {
        "count": int(arr.size),
        "rms_px": float(np.sqrt(np.mean(arr * arr))),
        "mean_px": float(np.mean(arr)),
        "p95_px": float(np.percentile(arr, 95)),
        "max_px": float(np.max(arr)),
    }


def _design_col_count(feature_count: int, degree: int) -> int:
    degree = int(max(1, degree))
    if degree <= 1:
        return 1 + feature_count
    return 1 + feature_count + feature_count + (feature_count * (feature_count - 1)) // 2


def _screen_design_col_count(degree: int) -> int:
    return 6 if int(max(1, degree)) >= 2 else 3


def _design_row(features: dict[str, float], keys: tuple[str, ...], degree: int) -> np.ndarray:
    base = np.asarray([_safe_float(features.get(key, 0.0)) for key in keys], dtype=float)
    parts: list[np.ndarray] = [np.asarray([1.0], dtype=float), base]
    if int(max(1, degree)) >= 2:
        parts.append(base * base)
        if len(base) >= 2:
            cross = [base[i] * base[j] for i in range(len(base)) for j in range(i + 1, len(base))]
            parts.append(np.asarray(cross, dtype=float))
    return np.concatenate(parts, axis=0)


def _screen_design_row(x: float, y: float, warp: ScreenWarpModel) -> np.ndarray:
    nx = (_safe_float(x) - warp.center_x) / max(1.0, warp.scale_x)
    ny = (_safe_float(y) - warp.center_y) / max(1.0, warp.scale_y)
    if int(max(1, warp.degree)) >= 2:
        return np.asarray([1.0, nx, ny, nx * nx, ny * ny, nx * ny], dtype=float)
    return np.asarray([1.0, nx, ny], dtype=float)


def _edge_weights(samples: Sequence[CalibrationSample], gain: float = 1.5) -> np.ndarray:
    g = max(0.0, float(gain))
    if not samples:
        return np.asarray([], dtype=float)
    xs = np.asarray([sample.target_x for sample in samples], dtype=float)
    ys = np.asarray([sample.target_y for sample in samples], dtype=float)
    min_x, max_x = float(np.min(xs)), float(np.max(xs))
    min_y, max_y = float(np.min(ys)), float(np.max(ys))
    w_x = max(1.0, max_x - min_x)
    w_y = max(1.0, max_y - min_y)
    nx = (xs - min_x) / w_x
    ny = (ys - min_y) / w_y
    edge_strength = (np.abs(nx - 0.5) + np.abs(ny - 0.5)) * 2.0
    return 1.0 + g * np.clip(edge_strength, 0.0, 1.0)


def _fit_core_model(
    samples: Sequence[CalibrationSample],
    keys: tuple[str, ...],
    *,
    degree: int,
    ridge: float,
    edge_weight_gain: float,
) -> LinearGazeModel | None:
    if len(samples) < max(6, len(keys) + 2):
        return None
    x_mat = np.asarray([_design_row(sample.features, keys, degree) for sample in samples], dtype=float)
    y_x = np.asarray([sample.target_x for sample in samples], dtype=float)
    y_y = np.asarray([sample.target_y for sample in samples], dtype=float)
    weights = _edge_weights(samples, gain=edge_weight_gain)
    sqrt_w = np.sqrt(weights)
    x_weighted = x_mat * sqrt_w[:, np.newaxis]
    y_x_weighted = y_x * sqrt_w
    y_y_weighted = y_y * sqrt_w
    cols = x_mat.shape[1]
    eye = np.eye(cols, dtype=float)
    eye[0, 0] = 0.0
    xtx = x_weighted.T @ x_weighted + max(0.0, float(ridge)) * eye
    try:
        inv = np.linalg.pinv(xtx)
    except np.linalg.LinAlgError:
        return None
    coeffs_x = inv @ x_weighted.T @ y_x_weighted
    coeffs_y = inv @ x_weighted.T @ y_y_weighted
    pred_x = x_mat @ coeffs_x
    pred_y = x_mat @ coeffs_y
    rms_error = float(np.sqrt(np.mean((pred_x - y_x) ** 2 + (pred_y - y_y) ** 2)))
    return LinearGazeModel(
        feature_keys=keys,
        coeffs_x=tuple(float(item) for item in coeffs_x.tolist()),
        coeffs_y=tuple(float(item) for item in coeffs_y.tolist()),
        rms_error_px=rms_error,
        degree=int(max(1, degree)),
    )


def _residuals_px(model: LinearGazeModel, samples: Sequence[CalibrationSample]) -> list[float]:
    out: list[float] = []
    for sample in samples:
        px, py = model.predict(sample.features)
        out.append(math.hypot(px - sample.target_x, py - sample.target_y))
    return out


def _rms_on_samples(model: LinearGazeModel, samples: Sequence[CalibrationSample]) -> float:
    errs = _residuals_px(model, samples)
    if not errs:
        return float("inf")
    arr = np.asarray(errs, dtype=float)
    return float(np.sqrt(np.mean(arr * arr)))
