"""Keep verified window names opaque to vocabulary checks, not factual checks."""
from __future__ import annotations

import json
import re


def without_observed_window_names(text: str, situation: object) -> str:
    """Mask complete observed names in a scratch copy; never change public prose.

    Only successful typed window observations supply vocabulary. Mission steps
    keep their own verification envelope; merged observations and dialogue do not.
    """
    names: set[str] = set()

    def collect(node: object, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except (ValueError, TypeError):
                return
        if not isinstance(node, dict):
            return
        if (node.get("kind") == "operation"
                and isinstance(node.get("operation"), str)
                and node["operation"].startswith("window.")
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            observed = node.get("observed")
            windows = observed.get("windows") if isinstance(observed, dict) else None
            if isinstance(windows, list):
                for window in windows:
                    if isinstance(window, dict):
                        names.update(value for key in ("title", "processName")
                                     if isinstance(value := window.get(key), str)
                                     and value.strip() and len(value) <= 4096)
        steps = node.get("steps")
        if isinstance(steps, list):
            for step in steps:
                collect(step, depth + 1)

    collect(situation)
    if not names:
        return text
    # Do not hide part of a dotted/hyphenated identifier. A sentence-ending dot
    # is punctuation, whereas a dot or hyphen followed by a word extends it.
    pattern = r"(?<![\w.-])(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r")(?!\w|[.-]\w)"
    return re.sub(pattern, "\ufffc", text, flags=re.IGNORECASE)
