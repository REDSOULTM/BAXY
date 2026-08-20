"""Measure the theoretical current-catalogue reach of inherited legacy tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for root in (REPO, REPO / "src"):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)

FRESH = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
OUTPUT = REPO / "artifacts" / "development" / "goal03_inherited_legacy_crosswalk_v32.json"

# Contract-only crosswalk. Each relation follows the legacy function description
# and the current typed operation descriptions; no fresh utterance is consulted.
LEGACY_TO_CURRENT: dict[str, tuple[str, ...]] = {
    "active": ("window.active",),
    "app_close": ("app.close",),
    "app_open": ("app.open", "game.launch"),
    "app_search": (
        "app.installed",
        "game.installed.named",
        "window.application.status",
    ),
    "battery": ("system.status",),
    "browser_open": (
        "browser.navigate",
        "browser.navigate.named",
        "streaming.navigate",
    ),
    "browser_search": ("web.search",),
    "describe_screen": ("capture.screenshot", "vision.describe"),
    "filesystem_delete": (
        "filesystem.known.trash.named",
        "filesystem.trash.prepare",
    ),
    "filesystem_list": ("filesystem.list",),
    "filesystem_read": ("filesystem.read.text",),
    "filesystem_search": (
        "filesystem.known.search",
        "filesystem.search",
    ),
    "get_system_resources": ("system.status",),
    "gui_click": ("input.pointer.control", "input.visible.click"),
    "gui_screenshot": ("capture.active.window", "capture.screenshot"),
    "knowledge_search": (),
    "library": ("game.catalog.list",),
    "maximize": ("window.maximize",),
    "media_next": ("media.control",),
    "media_previous": ("media.control",),
    "media_stop": ("media.control",),
    "memory_save": ("memory.save", "memory.sensitive.save"),
    "minimize": ("window.minimize",),
    "mkdir": ("filesystem.create.directory",),
    "mute": ("audio.microphone.mute", "audio.mute"),
    "pause": ("media.control",),
    "play": (
        "media.play.exact",
        "media.play.query",
        "media.play.youtube",
        "streaming.play.named",
    ),
    "processes": ("system.process.list",),
    "recall": ("memory.recall",),
    "resume": ("media.control",),
    "search_store": ("browser.navigate", "game.catalog.list"),
    "send_message": ("message.send",),
    "set_volume": ("audio.volume", "audio.volume.adjust"),
    "steam_open": ("app.open",),
    "store": ("browser.navigate", "game.catalog.list"),
    "store_page": ("browser.navigate", "game.catalog.list"),
    "terminal_run": (),
    "time": ("system.time",),
    "web_search": ("web.search",),
    "window_close": ("app.close",),
    "window_focus": ("window.focus",),
    "window_list": ("window.resolve",),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run(output: Path) -> dict[str, Any]:
    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    catalog = {str(row["name"]) for row in capabilities}
    mapped_operations = {
        operation
        for operations in LEGACY_TO_CURRENT.values()
        for operation in operations
    }
    unknown = sorted(mapped_operations - catalog)
    if unknown:
        raise RuntimeError(f"crosswalk names absent from current catalogue: {unknown}")

    rows = _jsonl(FRESH)
    inside = [row for row in rows if row.get("in_catalog")]
    covered = [
        row
        for row in inside
        if set(row.get("expected_operations") or []) & mapped_operations
    ]
    expected_operations = {
        operation
        for row in inside
        for operation in row.get("expected_operations") or []
    }
    covered_expected = expected_operations & mapped_operations
    report = {
        "schema": "baxy.goal03-inherited-legacy-crosswalk.v1",
        "fresh_corpus": {
            "path": str(FRESH.relative_to(REPO)),
            "sha256": _sha256(FRESH),
            "in_catalog_rows": len(inside),
            "distinct_expected_operations": len(expected_operations),
        },
        "current_catalogue_operations": len(catalog),
        "legacy_functions": len(LEGACY_TO_CURRENT),
        "legacy_functions_without_current_equivalent": sorted(
            name for name, operations in LEGACY_TO_CURRENT.items() if not operations
        ),
        "mapped_current_operations": len(mapped_operations),
        "mapped_current_operation_names": sorted(mapped_operations),
        "fresh_oracle_reach": {
            "covered_rows": len(covered),
            "total_rows": len(inside),
            "covered_distinct_expected_operations": len(covered_expected),
            "total_distinct_expected_operations": len(expected_operations),
            "covered_expected_operation_names": sorted(covered_expected),
            "uncovered_expected_operation_names": sorted(
                expected_operations - mapped_operations
            ),
        },
        "crosswalk": {key: list(value) for key, value in LEGACY_TO_CURRENT.items()},
        "effects_executed": 0,
        "providers_enabled": False,
        "source_projects_modified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--seal-only", action="store_true")
    args = parser.parse_args()
    if args.seal_only:
        print(json.dumps({key: list(value) for key, value in LEGACY_TO_CURRENT.items()}, indent=2, sort_keys=True))
        return 0
    report = run(args.output.resolve())
    print(json.dumps({key: value for key, value in report.items() if key != "crosswalk"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
