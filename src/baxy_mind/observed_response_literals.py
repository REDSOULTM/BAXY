"""Keep verified observed names opaque to vocabulary checks, not factual checks."""
from __future__ import annotations

import json
import re


def without_observed_names(text: str, situation: object) -> str:
    """Mask complete observed names in a scratch copy; never change public prose.

    Only successful typed observations supply vocabulary. Mission steps
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
        operation = node.get("operation")
        if (node.get("kind") == "operation"
                and isinstance(operation, str)
                and (operation.startswith("window.") or operation in {"system.process.list", "app.installed"})
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            observed = node.get("observed")
            if (operation == "app.installed" and isinstance(observed, dict)
                    and observed.get("authority") == "windows_start_catalog_snapshot"):
                # The provider's human-readable authority is observed data too.
                names.update(("catálogo de inicio de Windows", "Windows Start application catalog"))
            process_inventory = operation == "system.process.list"
            entries = observed.get("processes" if process_inventory else "windows") if isinstance(observed, dict) else None
            fields = ("name",) if process_inventory else ("title", "processName")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        names.update(value for key in fields
                                     if isinstance(value := entry.get(key), str)
                                     and value.strip() and len(value) <= 4096)
        if (node.get("kind") == "operation" and operation == "filesystem.known.list"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # FILES1425 «lista los archivos del escritorio»: a listed name is
            # observed data (dots, hyphens and underscores included).
            observed = node.get("observed")
            listed = observed.get("entries") if isinstance(observed, dict) else None
            if isinstance(listed, list):
                names.update(name.strip() for entry in listed if isinstance(entry, dict)
                             and isinstance(name := entry.get("name"), str)
                             and 0 < len(name.strip()) <= 4096)
        if (node.get("kind") == "operation" and operation == "ocr.read"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # SCREEN1411 «leéme lo que dice la pantalla»: the person asked for the
            # screen's words; a quoted recognized line (identifiers, paths and
            # dotted names included) is observed data, not vocabulary about BAXY.
            observed = node.get("observed")
            recognized = observed.get("text") if isinstance(observed, dict) else None
            if isinstance(recognized, str) and recognized.strip():
                names.update(line.strip() for line in recognized.split("\n")
                             if 1 < len(line.strip()) <= 4096)
                names.update(re.findall(r"[\w-]+(?:[._][\w-]+)+", recognized))
            # SCREEN1421: the provider joins `text` with spaces; the recognized
            # lines (what the composer quotes) live in layout.lines[].text.
            layout = observed.get("layout") if isinstance(observed, dict) else None
            layout_lines = layout.get("lines") if isinstance(layout, dict) else None
            if isinstance(layout_lines, list):
                names.update(line_text.strip() for line in layout_lines if isinstance(line, dict)
                             and isinstance(line_text := line.get("text"), str)
                             and 1 < len(line_text.strip()) <= 4096)
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
