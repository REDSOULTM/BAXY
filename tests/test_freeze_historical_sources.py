from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.freeze_historical_sources import (
    canonical_digest,
    codex_root_threads_snapshot,
    current_thread_prefix,
    dirty_status,
    file_manifest,
)


class FreezeHistoricalSourcesTests(unittest.TestCase):
    def test_canonical_digest_ignores_dictionary_insertion_order(self) -> None:
        self.assertEqual(
            canonical_digest({"b": 2, "a": 1}),
            canonical_digest({"a": 1, "b": 2}),
        )

    def test_thread_prefix_stops_at_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "thread.jsonl"
            before = {"timestamp": "2026-07-14T10:51:49.000Z", "value": 1}
            after = {"timestamp": "2026-07-14T10:51:50.000Z", "value": 2}
            path.write_text(
                json.dumps(before) + "\n" + json.dumps(after) + "\n",
                encoding="utf-8",
            )
            result = current_thread_prefix(
                path, datetime(2026, 7, 14, 10, 51, 49, 500000, tzinfo=timezone.utc)
            )
            self.assertEqual(result["line_count"], 1)
            first_line = path.read_bytes().splitlines(keepends=True)[0]
            self.assertEqual(result["bytes"], len(first_line))

    def test_file_manifest_hashes_evidence_and_summarizes_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "messages.jsonl").write_text('{"role":"user"}\n', encoding="utf-8")
            (root / "model.gguf").write_bytes(b"not-a-real-model")
            result = file_manifest(root, "fixture")
            self.assertEqual(result["file_count"], 1)
            self.assertEqual(result["files"][0]["path"], "messages.jsonl")
            self.assertEqual(result["excluded_summary"]["model_or_runtime"]["count"], 1)

    def test_dirty_status_preserves_spaces_and_unicode_without_git_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            path = root / "carpeta con espacio" / "señal.json"
            path.parent.mkdir()
            path.write_text("{}", encoding="utf-8")
            result = dirty_status(root)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["path"], "carpeta con espacio/señal.json")
            self.assertTrue(result[0]["exists"])

    def test_codex_root_threads_excludes_agent_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "agents.json"
            manifest.write_text(
                json.dumps({"records": [{"session_id": "agent-session"}]}),
                encoding="utf-8",
            )
            events = root / "sessions"
            events.mkdir()
            fixtures = {
                "root-session": {"source": "cli"},
                "agent-session": {},
                "unlisted-child": {
                    "parent_thread_id": "root-session",
                    "agent_path": "/root/audit",
                    "source": {"subagent": {"thread_spawn": {"depth": 1}}},
                },
            }
            for session_id, metadata in fixtures.items():
                path = events / f"{session_id}.jsonl"
                rows = [
                    {
                        "timestamp": "2026-07-14T10:00:00.000Z",
                        "payload": {
                            "session_id": "parent-thread",
                            "id": session_id,
                            "cwd": r"C:\Users\example\BAXY",
                            **metadata,
                        },
                    },
                    {"timestamp": "2026-07-14T10:01:00.000Z", "type": "message"},
                ]
                path.write_text(
                    "".join(json.dumps(row) + "\n" for row in rows),
                    encoding="utf-8",
                )
            (events / "future-session.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-07-14T11:00:00.000Z",
                        "payload": {
                            "id": "future-session",
                            "session_id": "future-session",
                            "cwd": r"C:\Users\example\BAXY",
                            "source": "cli",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = codex_root_threads_snapshot(
                events,
                datetime(2026, 7, 14, 10, 30, tzinfo=timezone.utc),
                manifest,
            )
            self.assertEqual(result["thread_count"], 1)
            self.assertEqual(result["records"][0]["session_id"], "root-session")


if __name__ == "__main__":
    unittest.main()
