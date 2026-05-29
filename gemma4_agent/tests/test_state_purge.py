"""Tests for AgentState.purge_stale_closed (Sprint 7.2).

The purge runs once on Gemma4Agent boot. It must:
  - Drop closed resources older than max_age_days.
  - Drop closed resources missing closed_at (legacy).
  - Drop closed resources with malformed closed_at.
  - NEVER touch open resources, regardless of age.
"""
from __future__ import annotations

import datetime as _dt
import json
import tempfile
import unittest
from pathlib import Path

from gemma4_agent.memory_pkg.state import AgentState


def _make_state(resources: dict) -> AgentState:
    """Build an AgentState pre-loaded with the given resources dict."""
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_state_purge_"))
    path = tmp / "state.json"
    payload = {
        "resources": resources,
        "checkpoints": {},
        "notes": [],
        "confirmations": {},
        "schedules": {},
        "downloads": {},
        "watchers": {},
        "routines": {},
        "jobs": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return AgentState(path)


def _iso_ago(days: float) -> str:
    """Return an ISO timestamp (with local tz) for N days ago."""
    moment = _dt.datetime.now().astimezone() - _dt.timedelta(days=days)
    return moment.isoformat(timespec="seconds")


class TestPurgeStaleClosed(unittest.TestCase):

    def test_keeps_recent_closed(self) -> None:
        state = _make_state({
            "res_recent": {"id": "res_recent", "kind": "x",
                           "status": "closed", "closed_at": _iso_ago(1)},
        })
        out = state.purge_stale_closed(max_age_days=7)
        self.assertTrue(out["ok"])
        self.assertEqual(out["purged"], 0)
        self.assertEqual(out["before"], 1)
        self.assertEqual(out["after"], 1)

    def test_drops_old_closed(self) -> None:
        state = _make_state({
            "res_old": {"id": "res_old", "kind": "x",
                        "status": "closed", "closed_at": _iso_ago(30)},
        })
        out = state.purge_stale_closed(max_age_days=7)
        self.assertEqual(out["purged"], 1)
        self.assertEqual(out["after"], 0)

    def test_drops_legacy_closed_without_closed_at(self) -> None:
        state = _make_state({
            "res_legacy": {"id": "res_legacy", "kind": "x",
                           "status": "closed"},  # no closed_at
        })
        out = state.purge_stale_closed(max_age_days=7)
        self.assertEqual(out["purged"], 1)

    def test_drops_malformed_closed_at(self) -> None:
        state = _make_state({
            "res_bad": {"id": "res_bad", "kind": "x",
                        "status": "closed", "closed_at": "not a real date"},
        })
        out = state.purge_stale_closed(max_age_days=7)
        self.assertEqual(out["purged"], 1)

    def test_never_drops_open_resources(self) -> None:
        # Open resource without closed_at, "old" by any definition — must stay.
        state = _make_state({
            "res_open": {"id": "res_open", "kind": "browser_real",
                         "status": "open"},
        })
        out = state.purge_stale_closed(max_age_days=7)
        self.assertEqual(out["purged"], 0)
        self.assertEqual(out["after"], 1)

    def test_mixed_population(self) -> None:
        state = _make_state({
            "open1":   {"id": "open1",   "kind": "x", "status": "open"},
            "fresh":   {"id": "fresh",   "kind": "x", "status": "closed",
                        "closed_at": _iso_ago(1)},
            "old":     {"id": "old",     "kind": "x", "status": "closed",
                        "closed_at": _iso_ago(30)},
            "legacy":  {"id": "legacy",  "kind": "x", "status": "closed"},
        })
        out = state.purge_stale_closed(max_age_days=7)
        self.assertEqual(out["before"], 4)
        self.assertEqual(out["after"], 2)  # open1 + fresh stay
        self.assertEqual(out["purged"], 2)

    def test_idempotent(self) -> None:
        # Two consecutive purges: second one should be a no-op.
        state = _make_state({
            "fresh": {"id": "fresh", "kind": "x", "status": "closed",
                      "closed_at": _iso_ago(1)},
            "old": {"id": "old", "kind": "x", "status": "closed",
                    "closed_at": _iso_ago(30)},
        })
        first = state.purge_stale_closed(max_age_days=7)
        second = state.purge_stale_closed(max_age_days=7)
        self.assertEqual(first["purged"], 1)
        self.assertEqual(second["purged"], 0)

    def test_persists_to_disk(self) -> None:
        # The purge must actually write the trimmed state.json so the
        # change survives an AgentState reload.
        state = _make_state({
            "old": {"id": "old", "kind": "x", "status": "closed",
                    "closed_at": _iso_ago(30)},
        })
        state.purge_stale_closed(max_age_days=7)
        # Reload from disk via a fresh instance pointing to the same path.
        reloaded = AgentState(state.path)
        listing = reloaded.list_resources(include_closed=True)
        self.assertNotIn("old", {r["id"] for r in listing["resources"]})


if __name__ == "__main__":
    unittest.main()
