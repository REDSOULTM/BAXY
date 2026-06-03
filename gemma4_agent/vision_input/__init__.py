"""Deterministic webcam input subsystem for Gemma 4.

Phase 0 is a measurement-only POC: webcam capture, MediaPipe landmarks,
geometry gestures, coarse head pointer, overlay, and reports. It does not call
the LLM and does not execute GUI actions.
"""
from __future__ import annotations

__all__ = [
    "camera",
    "calibration",
    "controller",
    "gestures",
    "gaze",
    "landmarks",
    "monitors",
    "pointer",
    "snap",
    "watchers",
    "window_control",
    "window_target",
]
