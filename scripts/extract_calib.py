import sys

with open('gemma4_agent/vision_input/window_control.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

flow_lines = []
main_lines = []

def is_calib_func(line):
    funcs = [
        'def _bad_validation_targets(',
        'def _validation_summary(',
        'def _validation_summary_passes(',
        'def _validation_notice(',
        'def _fit_validation_screen_warp(',
        'def _handle_calibration_keys(',
        'def _handle_validation_keys(',
        'def _save_calibration_profile(',
        'def _save_calibration_debug_capture(',
        'def _online_retrain_from_clicks(',
        'def _make_validation_sample(',
        'def _average_points(',
        'def _head_confident_for_online_learn(',
        'def _merge_calibration_samples(',
        'def _merge_keys(',
        'def _has_capture_key(',
        'def _set_cursor_pos(',
        'def _error_summary(',
        'def _monitor_index_for_point(',
        'def _head_debug_payload(',
        'def _sample_from_click_history(',
        'def _append_online_feature_snapshot('
    ]
    return any(line.startswith(fn) for fn in funcs)

i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('@dataclass'):
        if i + 1 < len(lines) and lines[i+1].startswith('class ValidationSample:'):
            flow_lines.append(line)
            i += 1
            flow_lines.append(lines[i])
            i += 1
            while i < len(lines) and (lines[i].startswith(' ') or lines[i].strip() == ''):
                flow_lines.append(lines[i])
                i += 1
            continue
    
    if is_calib_func(line):
        flow_lines.append(line)
        i += 1
        while i < len(lines) and (lines[i].startswith(' ') or lines[i].strip() == '' or lines[i].startswith(') ->')):
            if lines[i].startswith('def '):
                break
            flow_lines.append(lines[i])
            i += 1
        continue

    main_lines.append(line)
    i += 1

with open('gemma4_agent/vision_input/calibration_flow.py', 'w', encoding='utf-8') as f:
    f.write('"""Calibration state machine and validation utilities."""\n')
    f.write('from __future__ import annotations\n')
    f.write('import argparse, math, json, os, getpass\n')
    f.write('from dataclasses import dataclass, asdict\n')
    f.write('from datetime import datetime\n')
    f.write('from collections import deque\n')
    f.write('from pathlib import Path\n')
    f.write('from typing import Any\n')
    f.write('import numpy as np\n')
    f.write('from .calibration import (\n')
    f.write('    CalibrationProfile, CalibrationSample, CalibrationStore, LinearGazeModel,\n')
    f.write('    fit_linear_model, fit_monitor_corrections, fit_screen_warp, with_monitor_corrections, with_screen_warp\n')
    f.write(')\n')
    f.write('from .pointer import HeadPointerEstimate\n')
    f.write('from .monitors import VirtualCanvas, canvas_to_dict\n')
    f.write('from .window_control import KEY_QUIT, KEY_CALIBRATION_CLEAR, KEY_CALIBRATION_NEXT, KEY_CALIBRATION_CAPTURE, KEY_CALIBRATION_SAVE, ONLINE_FEATURE_KEYS, _feature_jitter, _average_features, _head_features\n')
    f.write('\n')
    f.writelines(flow_lines)

with open('gemma4_agent/vision_input/window_control_new.py', 'w', encoding='utf-8') as f:
    f.writelines(main_lines)

print('Extracted', len(flow_lines), 'lines to calibration_flow.py')
