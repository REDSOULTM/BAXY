from __future__ import annotations

import argparse
from pathlib import Path

from .poc import (
    DEFAULT_CAMERA_BACKEND,
    DEFAULT_CAMERA_HEIGHT,
    DEFAULT_CAMERA_INDEX,
    DEFAULT_CAMERA_WIDTH,
)

KEY_QUIT = {ord("q"), ord("Q"), 27}
# Support both ASCII and Win32 virtual-key OEM codes.
KEY_TOGGLE_EXECUTE = {ord("."), 0xBE, 0x6E}
KEY_TOGGLE_CALIBRATION = {ord(","), 0xBC, ord("k"), ord("K")}
KEY_RESTART_CALIBRATION = {ord("p"), ord("P")}
KEY_CALIBRATION_CAPTURE = {32, ord("s"), ord("S")}
KEY_CALIBRATION_SAVE = {10, 13}
KEY_CALIBRATION_NEXT = {ord("n"), ord("N")}
KEY_CALIBRATION_CLEAR = {ord("c"), ord("C")}
ONLINE_FEATURE_KEYS = ("yaw", "pitch", "gaze_x", "gaze_y")



def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma 4 camera window-control Phase 1 POC")
    parser.add_argument("--camera-index", type=int, default=DEFAULT_CAMERA_INDEX)
    parser.add_argument("--camera-backend", choices=("any", "dshow", "msmf"), default=DEFAULT_CAMERA_BACKEND)
    parser.add_argument("--quiet-runtime-logs", dest="quiet_runtime_logs", action="store_true", default=True)
    parser.add_argument("--verbose-runtime-logs", dest="quiet_runtime_logs", action="store_false")
    parser.add_argument("--list-cameras", action="store_true")
    parser.add_argument("--camera-scan-limit", type=int, default=8)
    parser.add_argument("--width", type=int, default=DEFAULT_CAMERA_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_CAMERA_HEIGHT)
    parser.add_argument("--camera-fps", type=int, default=30)
    # The cursor follows the HEAD, so the face model must run every frame here —
    # face_every_n>1 only updated the cursor every Nth frame (the dominant cause
    # of "laggy/steppy" tracking: at ~15 FPS, n=4 refreshed the cursor ~4x/sec).
    # The POC (measurement-only) can still skip frames; window control should not.
    parser.add_argument("--face-every-n", type=int, default=1)
    parser.add_argument("--iris-refine", dest="iris_refine", action="store_true", default=True)
    parser.add_argument("--no-iris-refine", dest="iris_refine", action="store_false")
    parser.add_argument("--gaze-gain-x", type=float, default=0.62)
    parser.add_argument("--gaze-gain-y", type=float, default=0.42)
    parser.add_argument("--gaze-deadzone", type=float, default=0.025)
    parser.add_argument("--no-auto-center", action="store_true", help="Disable adaptive center for camera placement.")
    parser.add_argument("--auto-center-alpha", type=float, default=0.03)
    # Responsiveness of the cursor. alpha is the EMA catch-up fraction per frame
    # (higher = snappier, lower = smoother but laggier); max-step caps per-frame
    # travel before the EMA. The old 0.16 / 180px felt sluggish: at ~15 FPS the
    # cursor needed many frames to reach a new target and was speed-capped across
    # the desktop. 0.45 / 600px tracks the head with little perceptible lag while
    # the one-euro filter upstream still absorbs jitter.
    parser.add_argument("--gaze-smooth-alpha", type=float, default=0.45)
    parser.add_argument("--gaze-max-step-px", type=float, default=600.0)
    parser.add_argument("--use-calibration", dest="use_calibration", action="store_true", default=True)
    parser.add_argument("--no-use-calibration", dest="use_calibration", action="store_false")
    parser.add_argument("--reset-calibration-history", action="store_true")
    parser.add_argument("--run-calibration", action="store_true", help="Collect gaze samples and save a calibrated model.")
    parser.add_argument("--control-after-calibration", dest="control_after_calibration", action="store_true", default=True)
    parser.add_argument("--no-control-after-calibration", dest="control_after_calibration", action="store_false")
    parser.add_argument("--merge-calibration-history", dest="merge_calibration_history", action="store_true", default=False)
    parser.add_argument("--no-merge-calibration-history", dest="merge_calibration_history", action="store_false")
    parser.add_argument("--calibration-history-max-samples", type=int, default=1200)
    parser.add_argument("--calibration-min-samples", type=int, default=5)
    parser.add_argument("--calibration-avg-frames", type=int, default=8)
    parser.add_argument("--calibration-min-capture-frames", type=int, default=2)
    parser.add_argument("--calibration-max-feature-jitter", type=float, default=0.080)
    parser.add_argument("--calibration-min-gaze-confidence", type=float, default=0.60)
    parser.add_argument("--calibration-max-rms-px", type=float, default=3000.0)
    parser.add_argument("--calibration-user", type=str, default=None)
    parser.add_argument("--validate-after-calibration", dest="validate_after_calibration", action="store_true", default=True)
    parser.add_argument("--no-validate-after-calibration", dest="validate_after_calibration", action="store_false")
    parser.add_argument("--require-validation-for-actions", dest="require_validation_for_actions", action="store_true", default=True)
    parser.add_argument("--no-require-validation-for-actions", dest="require_validation_for_actions", action="store_false")
    parser.add_argument("--validation-points-per-monitor", type=int, choices=(5, 9), default=5)
    parser.add_argument("--validation-avg-frames", type=int, default=8)
    parser.add_argument("--validation-min-capture-frames", type=int, default=2)
    parser.add_argument("--validation-max-rms-px", type=float, default=220.0)
    parser.add_argument("--validation-max-p95-px", type=float, default=380.0)
    parser.add_argument("--validation-min-monitor-accuracy", type=float, default=0.95)
    parser.add_argument("--validation-max-point-error-px", type=float, default=520.0)
    parser.add_argument("--validation-repeat-worst", type=int, default=8)
    parser.add_argument(
        "--validation-max-retries",
        type=int,
        default=1,
        help="How many failed validation rounds can send you back to repeat bad points before falling back to SAFE mode.",
    )
    parser.add_argument("--fine-screen-warp", dest="fine_screen_warp", action="store_true", default=True)
    parser.add_argument("--no-fine-screen-warp", dest="fine_screen_warp", action="store_false")
    parser.add_argument("--fine-screen-warp-max-rms-px", type=float, default=180.0)
    parser.add_argument(
        "--save-calibration-debug-captures",
        action="store_true",
        help="Opt-in privacy debug: save one camera PNG + JSON metadata for each Space/s calibration or validation capture.",
    )
    parser.add_argument("--debug-capture-dir", type=Path, default=Path("test") / "eye_tracking_captures")
    parser.add_argument("--auto-online-learn", action="store_true", help="Disabled/no-op for now; kept only for CLI compatibility.")
    parser.add_argument("--online-learn-min-gaze-confidence", type=float, default=0.62)
    parser.add_argument("--online-learn-min-samples", type=int, default=18)
    parser.add_argument("--online-learn-retrain-every", type=int, default=8)
    parser.add_argument("--online-learn-max-new-samples", type=int, default=240)
    parser.add_argument("--online-learn-click-lag-ms", type=float, default=130.0)
    parser.add_argument("--online-learn-window-ms", type=float, default=180.0)
    parser.add_argument("--online-learn-max-feature-jitter", type=float, default=0.050)
    parser.add_argument("--online-learn-max-click-distance-px", type=float, default=340.0)
    parser.add_argument("--online-learn-history-max-frames", type=int, default=120)
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run; 0 means until q/esc.")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--mirror", dest="mirror", action="store_true", default=True)
    parser.add_argument("--no-mirror", dest="mirror", action="store_false")
    parser.add_argument("--download-models", action="store_true")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--num-hands", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--stabilizer-window", type=int, default=3, help=argparse.SUPPRESS)
    parser.add_argument("--gesture-enter-frames", type=int, default=2)
    parser.add_argument("--gesture-exit-frames", type=int, default=2)
    parser.add_argument("--gesture-min-confidence", type=float, default=0.50)
    parser.add_argument("--hand-min-score", type=float, default=0.45)
    parser.add_argument("--hand-edge-margin", type=float, default=0.035)
    parser.add_argument("--hand-max-jump-norm", type=float, default=0.28)
    parser.add_argument("--hand-min-palm-size", type=float, default=0.035)
    parser.add_argument("--hand-max-palm-size", type=float, default=0.55)
    parser.add_argument("--hand-min-two-hand-distance", type=float, default=0.085)
    parser.add_argument("--target-stable-ms", type=int, default=350)
    parser.add_argument("--target-search-radius-px", type=int, default=220)
    parser.add_argument("--target-foreground-fallback", dest="target_foreground_fallback", action="store_true", default=True)
    parser.add_argument("--no-target-foreground-fallback", dest="target_foreground_fallback", action="store_false")
    parser.add_argument("--execute-actions", action="store_true")
    parser.add_argument("--drag-gain-x-px", type=float, default=2600.0)
    parser.add_argument("--drag-gain-y-px", type=float, default=1500.0)
    parser.add_argument("--drag-smoothing-alpha", type=float, default=0.45)
    parser.add_argument("--drag-max-step-px", type=int, default=180)
    parser.add_argument("--scroll-threshold-norm", type=float, default=0.035)
    parser.add_argument("--scroll-gain", type=float, default=3600.0)
    parser.add_argument("--scroll-rearm-threshold-norm", type=float, default=0.012)
    parser.add_argument("--scroll-min-wheel-delta", type=int, default=120)
    parser.add_argument("--scroll-max-wheel-delta", type=int, default=360)
    parser.add_argument("--resize-ratio-smoothing-alpha", type=float, default=0.30)
    parser.add_argument("--resize-step-px", type=int, default=24)
    parser.add_argument("--maximize-ratio", type=float, default=1.55)
    parser.add_argument("--restore-ratio", type=float, default=0.65)
    parser.add_argument("--two-hand-zoom-step-ratio", type=float, default=0.12)
    parser.add_argument("--two-hand-zoom-cooldown-s", type=float, default=0.22)
    parser.add_argument("--point-click-cooldown-s", type=float, default=0.70)
    parser.add_argument("--point-snap-radius-px", type=int, default=320)
    parser.add_argument("--point-tap-threshold-norm", type=float, default=0.14)
    parser.add_argument("--point-tap-release-norm", type=float, default=0.055)
    parser.add_argument("--window-snap", dest="window_snap", action="store_true", default=True)
    parser.add_argument("--no-window-snap", dest="window_snap", action="store_false")
    parser.add_argument("--window-snap-edge-px", type=int, default=72)
    parser.add_argument("--event-log-size", type=int, default=80)
    parser.add_argument("--show-gaze-pointer", dest="show_gaze_pointer", action="store_true", default=True)
    parser.add_argument("--no-gaze-pointer", dest="show_gaze_pointer", action="store_false")
    parser.add_argument("--show-desktop-map", dest="show_desktop_map", action="store_true", default=True)
    parser.add_argument("--no-desktop-map", dest="show_desktop_map", action="store_false")
    parser.add_argument("--show-desktop-gaze-dot", dest="show_desktop_gaze_dot", action="store_true", default=True)
    parser.add_argument("--no-desktop-gaze-dot", dest="show_desktop_gaze_dot", action="store_false")
    parser.add_argument("--desktop-gaze-dot-size", type=int, default=44)
    parser.add_argument("--show-system-gaze-pointer", dest="show_system_gaze_pointer", action="store_true", default=False)
    parser.add_argument("--no-system-gaze-pointer", dest="show_system_gaze_pointer", action="store_false")
    parser.add_argument(
        "--global-hotkeys",
        action="store_true",
        help="Listen for q/Esc globally even if OpenCV window is unfocused.",
    )
    parser.add_argument("--report-path", type=Path, default=None)
    return parser.parse_args(argv)
