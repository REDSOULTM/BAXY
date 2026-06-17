"""Deterministic hand-gesture recognition from 21 MediaPipe landmarks."""
from __future__ import annotations

import math
import os
import pickle
from collections import deque
from dataclasses import dataclass, field

from .landmarks import HandSample, NormalizedPoint

# Clasificador RF OPT-IN (GEMMA4_GESTURE_ML=1, lo activan los entrypoints de
# runtime — controller/standalone). El modelo se entrena con los videos del
# OPERADOR (train_model.py) = personalización legítima para SU sesión de
# cámara, pero NO puede ser el default del módulo: el gate de calidad
# UNIVERSAL (fixture kinivi, manos diversas Apache-2.0) mide la heurística y
# un RF personal lo degrada para cualquier otra mano (regla de universalidad
# del README). Carga LAZY: ni el import paga el pickle.
_ML_STATE: dict = {"loaded": False, "model": None}


def _ml_enabled() -> bool:
    return (os.environ.get("GEMMA4_GESTURE_ML", "0") or "0").strip().lower() \
        in {"1", "true", "yes", "on"}


def _ml_model():
    if not _ML_STATE["loaded"]:
        _ML_STATE["loaded"] = True
        try:
            model_path = os.path.join(os.path.dirname(__file__),
                                      "gesture_rf_model.pkl")
            if os.path.exists(model_path):
                with open(model_path, "rb") as f:
                    _ML_STATE["model"] = pickle.load(f)
        except Exception:
            _ML_STATE["model"] = None
    return _ML_STATE["model"]


GESTURES = ("none", "unknown", "fist", "pinch", "palm", "point", "two_fingers")

# Below this wrist->middle-MCP distance (normalized image units) the hand is
# considered degenerate (collapsed landmarks / tracking failure). A real hand
# at usable distance spans well above this; this only catches the all-zero /
# all-identical pathological input.
_DEGENERATE_PALM_EPS = 1e-3

FINGER_JOINTS = {
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}


@dataclass(frozen=True)
class GestureThresholds:
    # Finger is "extended" above this MCP-PIP-TIP angle, "flexed" below the other.
    # Hysteresis band 132-152 deg avoids flicker. Tuned for MediaPipe Hands.
    extended_angle_deg: float = 152.0
    flexed_angle_deg: float = 132.0
    # thumb_tip<->index_tip distance / palm size, below which a pinch is possible.
    pinch_palm_ratio: float = 0.42
    # thumb tip must sit this far (x palm) from the palm center to count as "open".
    thumb_open_ratio: float = 0.85
    # Max non-index fingers allowed flexed for a pinch (a real pinch keeps the
    # other fingers extended; a fist flexes them all). Measured: 14->0 fist->pinch.
    pinch_max_flex: int = 1
    # Pinch "natural" con los demás dedos FLEXIONADOS (así lo hace gente real:
    # medido en los videos de scroll del operador, donde la regla pinch_max_flex
    # lo leía como fist y el scroll universal daba accuracy 0.0). Tres señales:
    # contacto casi cerrado (más estricto que pinch_palm_ratio), pulgar en la
    # PUNTA del índice (no en su PIP, donde cruza en el puño), y el índice
    # alcanzando AL FRENTE para formar el anillo — en el puño el índice se
    # curva HACIA la palma. Separación MEDIDA: fists kinivi que se fugaban
    # tienen wrist->index_tip <= 0.88·palm; el pinch real del operador da
    # p5 = 1.09 (scroll) / 1.40 (zoom). Gate kinivi: fist->pinch sigue en 0.
    pinch_flexed_max_ratio: float = 0.25
    pinch_tip_vs_pip_ratio: float = 0.8
    pinch_index_reach_min: float = 1.0
    # Point gesture: index must out-reach the longest other finger by this factor
    # and ALL three other fingers must be folded/short. Measured on the kinivi
    # fixture: palm accuracy 0.928 -> 0.992 (kills the open-palm->point confusion).
    point_index_dominance: float = 1.18
    point_min_folded_others: int = 3


@dataclass(frozen=True)
class GestureResult:
    label: str
    confidence: float
    pinch_distance: float | None = None
    finger_extended: dict[str, bool] = field(default_factory=dict)
    finger_flexed: dict[str, bool] = field(default_factory=dict)


class GestureStabilizer:
    """Small majority-vote stabilizer to reduce label flicker."""

    def __init__(self, window: int = 5) -> None:
        self.window = max(1, int(window))
        self._labels: deque[str] = deque(maxlen=self.window)
        self._stable = "none"

    def update(self, label: str) -> str:
        self._labels.append(label)
        counts: dict[str, int] = {}
        for item in self._labels:
            counts[item] = counts.get(item, 0) + 1
        best_label, best_count = max(counts.items(), key=lambda kv: kv[1])
        if counts.get(self._stable, 0) == best_count:
            return self._stable
        self._stable = best_label
        return self._stable

    def reset(self) -> None:
        self._labels.clear()
        self._stable = "none"


def extract_features(lm, palm, palm_center):
    # ORDEN DE FEATURES = contrato del RF (train_model.py extrae el mismo vector
    # al entrenar; cambiarlo invalida gesture_rf_model.pkl).
    features = []
    for name, (mcp, pip, tip) in FINGER_JOINTS.items():
        features.append(_angle_deg(lm[mcp], lm[pip], lm[tip]))
    for name, (mcp, pip, tip) in FINGER_JOINTS.items():
        features.append(_dist(lm[0], lm[tip]))
        features.append(_dist(lm[0], lm[pip]))
    features.append(_dist(lm[4], palm_center) / palm)
    features.append(_dist(lm[4], lm[8]) / palm)
    features.append(_dist(lm[0], lm[8]) / palm)
    return features


def recognize_hand_gesture(
    hand: HandSample | None,
    thresholds: GestureThresholds | None = None,
) -> GestureResult:
    if hand is None:
        return GestureResult("none", 1.0, 1.0, {}, {})

    th = thresholds or GestureThresholds()
    lm = hand.landmarks
    if len(lm) < 21:
        return GestureResult("unknown", 0.0)

    raw_palm = _dist(lm[0], lm[9])
    # Degeneration guard (RESTAURADA — el refactor la había perdido): landmarks
    # colapsados/casi idénticos (fallo de tracking) caían a "fist" 0.92 y
    # disparaban un grab/drag sobre basura. Incertidumbre honesta en su lugar
    # (honestidad estructural, mandamiento #3). Va ANTES del RF y la heurística.
    if raw_palm < _DEGENERATE_PALM_EPS:
        return GestureResult("unknown", 0.0)
    palm = max(raw_palm, 1e-6)
    palm_center = _mean_point(lm[0], lm[5], lm[9], lm[13], lm[17])
    
    extended: dict[str, bool] = {}
    flexed: dict[str, bool] = {}
    angles: dict[str, float] = {}
    tip_distances: dict[str, float] = {}
    pip_distances: dict[str, float] = {}
    
    for name, (mcp, pip, tip) in FINGER_JOINTS.items():
        angle = _angle_deg(lm[mcp], lm[pip], lm[tip])
        tip_distance = _dist(lm[0], lm[tip])
        pip_distance = _dist(lm[0], lm[pip])
        angles[name] = angle
        tip_distances[name] = tip_distance
        pip_distances[name] = pip_distance
        tip_farther = tip_distance > pip_distance * 1.02
        mcp_tip_dist = _dist(lm[mcp], lm[tip])
        # Foreshortening: un dedo apuntando A la cámara proyecta corto aunque
        # esté extendido. 0.6 era demasiado agresivo y rompía el gate de point
        # del fixture (0.944<0.95: índices apuntando leían flexed→fist).
        # MEDIDO en el fixture kinivi: 0.5 recupera point sin perder palm/fist.
        is_foreshortened = mcp_tip_dist < palm * 0.5
        extended[name] = angle >= th.extended_angle_deg and tip_farther and not is_foreshortened
        flexed[name] = angle <= th.flexed_angle_deg or not tip_farther or is_foreshortened

    pinch_distance = _dist(lm[4], lm[8]) / palm

    _ml = _ml_model() if _ml_enabled() else None
    if _ml is not None:
        try:
            feats = extract_features(lm, palm, palm_center)
            pred = _ml.predict([feats])[0]
            probs = _ml.predict_proba([feats])[0]
            conf = max(probs)
            # If the model is not very confident, fall back to "none"
            if conf < 0.4:
                pred = "none"
            
            # Allow heuristic FIST if ML model says 'none', to fix low fist recall.
            # Require idx_palm_dist < 0.95 to prevent confusing it with a PINCH
            # (where index is extended forward). La condición de mano vertical
            # (wrist y > knuckles y) se retiró: era un anti-falso de caras, pero
            # mataba el latigazo real (la mano ROTA durante el flick — medido:
            # el RF perdía la misión en Latigazo.mp4) y la zona de exclusión
            # facial con memoria es ahora el guard correcto para caras.
            idx_palm_dist = _dist(lm[0], lm[8]) / palm
            if pred == "none" and sum(1 for v in flexed.values() if v) >= 4:
                if idx_palm_dist < 0.95 and pinch_distance > 0.3:
                    pred = "fist"
                    conf = 0.90
            
            # Map model predictions to expected GestureResult format
            # ML "none" → GestureResult "unknown" (so the stabilizer sees an inactive gesture)
            output_label = "unknown" if pred == "none" else pred
            output_conf = 1.0 if pred == "none" else conf
            return GestureResult(output_label, output_conf, pinch_distance, extended, flexed)
        except Exception:
            pass
            
    # --- FALLBACK HEURISTICS ---
    thumb_open = _dist(lm[4], palm_center) > palm * th.thumb_open_ratio
    ext_count = sum(1 for v in extended.values() if v)
    flex_count = sum(1 for v in flexed.values() if v)

    # A real pinch is thumb+index touching while the OTHER fingers stay extended
    # (vocabulary doc §7). A curling fist also brings thumb and index close, so
    # without this the fist->pinch confusion fires a false click. Requiring at
    # most one non-index finger flexed separates pinch from fist.
    # Measured on the kinivi fixture: fist accuracy 0.920 -> 0.952, fist->pinch
    # 14 -> 0 (test_vision_input_gesture_fixture).
    if pinch_distance <= th.pinch_palm_ratio and flex_count <= th.pinch_max_flex:
        confidence = max(0.55, min(0.99, 1.0 - pinch_distance))
        return GestureResult("pinch", confidence, pinch_distance, extended, flexed)
    # Pinch flexionado (ver GestureThresholds.pinch_flexed_max_ratio): contacto
    # casi cerrado + pulgar en el TIP del índice (no en el PIP, como en el puño)
    # + índice alcanzando al frente (en el puño se curva hacia la palma).
    if pinch_distance <= th.pinch_flexed_max_ratio:
        thumb_to_index_pip = _dist(lm[4], lm[6]) / palm
        index_reach = _dist(lm[0], lm[8]) / palm
        if (
            pinch_distance < thumb_to_index_pip * th.pinch_tip_vs_pip_ratio
            and index_reach >= th.pinch_index_reach_min
        ):
            confidence = max(0.55, min(0.95, 1.0 - pinch_distance))
            return GestureResult("pinch", confidence, pinch_distance, extended, flexed)
    if flex_count >= 4:
        return GestureResult("fist", 0.92, pinch_distance, extended, flexed)
    if _looks_like_point(extended, flexed, angles, tip_distances, pip_distances, th):
        return GestureResult("point", 0.9, pinch_distance, extended, flexed)
    if extended["index"] and extended["middle"] and flexed["ring"] and flexed["pinky"]:
        return GestureResult("two_fingers", 0.88, pinch_distance, extended, flexed)
    if ext_count >= 3 and flex_count <= 1:
        confidence = 0.95 if thumb_open and ext_count >= 4 else 0.82
        return GestureResult("palm", confidence, pinch_distance, extended, flexed)
    return GestureResult("unknown", 0.35, pinch_distance, extended, flexed)


def _dist(a: NormalizedPoint, b: NormalizedPoint) -> float:
    # 2D only: MediaPipe's z is depth-relative-to-wrist with no coherent metric
    # scale (sometimes negative, not normalized — google/mediapipe#742). Using it
    # in raw 3D distances injects noise and breaks depth-invariance (a palm tilted
    # toward the camera reads as a fist). Classify on x,y; z is a weak signal at
    # most and is handled separately (controller air-tap), not here.
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _angle_deg(a: NormalizedPoint, b: NormalizedPoint, c: NormalizedPoint) -> float:
    ab = (a.x - b.x, a.y - b.y)
    cb = (c.x - b.x, c.y - b.y)
    dot = ab[0] * cb[0] + ab[1] * cb[1]
    mag = math.sqrt(sum(v * v for v in ab)) * math.sqrt(sum(v * v for v in cb))
    if mag <= 1e-9:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def _mean_point(*points: NormalizedPoint) -> NormalizedPoint:
    n = float(len(points))
    return NormalizedPoint(
        sum(p.x for p in points) / n,
        sum(p.y for p in points) / n,
        sum(p.z for p in points) / n,
    )


def _looks_like_point(
    extended: dict[str, bool],
    flexed: dict[str, bool],
    angles: dict[str, float],
    tip_distances: dict[str, float],
    pip_distances: dict[str, float],
    thresholds: GestureThresholds,
) -> bool:
    # 138.0 / 1.08: an index that is nearly straight (angle) and clearly longer
    # than its own PIP counts as extended even if it just misses the global
    # extended_angle threshold. 0.88: a non-index finger is "short" if its tip is
    # this fraction of the index tip reach. Constants tuned on the kinivi fixture.
    index_extended = (
        extended["index"]
        or (angles["index"] >= 138.0 and tip_distances["index"] > pip_distances["index"] * 1.08)
    )
    if not index_extended:
        return False
    other_names = ("middle", "ring", "pinky")
    folded_or_short = 0
    for name in other_names:
        if flexed[name] or tip_distances[name] < tip_distances["index"] * 0.88:
            folded_or_short += 1
    index_dominant = (
        tip_distances["index"]
        > max(tip_distances[name] for name in other_names) * thresholds.point_index_dominance
    )
    return folded_or_short >= thresholds.point_min_folded_others and index_dominant
