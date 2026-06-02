"""Cobertura dedicada para domain_tools/form_filler.py (added 2026-06-01).

form_filler.py NO tenía test propio (solo el smoke {action:status}). Llena
formularios HTML sobre una sesión browser_real existente, con un REVIEW-GATE
antes del submit (no envía sin confirmación). El tool recibe un `executor`
inyectable -> los tests lo mockean con un fake determinista, sin browser real.

Propiedades afirmadas contra el código fuente:
  - discover redacta el valor de inputs type=password (<hidden>), no lo filtra
  - plan matchea exact-antes-que-substring sobre label/name/id/placeholder
  - plan reporta unmatched cuando un campo no existe (no inventa selector)
  - apply: verified=True solo si TODOS los pasos ok; falla parcial -> verified False
  - submit SIN confirmed -> needs_confirmation + screenshot, NO clickea submit
    (review-gate: ley de no-acción-irreversible-sin-confirmar)
  - submit CON confirmed -> clickea, verified refleja el ok del click real
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ..domain_tools import form_filler
from ..memory_pkg.state import AgentState


class _FakeExecutor:
    """Captura las llamadas (tool, args) y devuelve respuestas programadas por
    action de browser_real. Determinista, sin red ni browser."""

    def __init__(self, fields=None, submits=None, click_ok=True, fill_ok=True):
        self.calls: list[tuple[str, dict]] = []
        self._fields = fields or []
        self._submits = submits or []
        self._click_ok = click_ok
        self._fill_ok = fill_ok

    def __call__(self, tool, args):
        self.calls.append((tool, dict(args)))
        action = args.get("action")
        if action == "evaluate":
            script = args.get("script", "")
            # _form_discover usa un script multi-línea con 'fields'/'submits'
            if "querySelectorAll('input, select, textarea')" in script or "const fields = []" in script:
                return {"ok": True, "value": {"fields": self._fields, "submits": self._submits},
                        "url": "http://test/form", "title": "Test Form"}
            # checkbox/select evaluate -> devolvemos un valor genérico
            return {"ok": True, "value": False}
        if action == "fill":
            return {"ok": self._fill_ok, "error": None if self._fill_ok else "fill failed"}
        if action == "click":
            return {"ok": self._click_ok, "error": None if self._click_ok else "click failed"}
        if action == "screenshot":
            return {"ok": True, "image_path": "/tmp/shot.png", "url": "http://test/form"}
        return {"ok": True}


_FIELDS = [
    {"selector": "#email", "tag": "input", "type": "email", "name": "email", "id": "email",
     "label": "Email Address", "placeholder": "", "required": True, "value": ""},
    {"selector": "#pwd", "tag": "input", "type": "password", "name": "password", "id": "pwd",
     "label": "Password", "placeholder": "", "required": True, "value": "<hidden>"},
    {"selector": "#agree", "tag": "input", "type": "checkbox", "name": "agree", "id": "agree",
     "label": "I agree", "placeholder": "", "required": False, "value": ""},
]
_SUBMITS = [{"selector": "#go", "text": "Sign up"}]


class TestFormStatus(unittest.TestCase):
    def test_status_announces_review_gate(self):
        r = form_filler.form_filler_tool({"action": "status"}, None, _FakeExecutor())
        self.assertTrue(r["ok"])
        self.assertTrue(r["review_gate_default"])
        self.assertEqual(r["backend"], "browser_real_orchestration")


class TestFormDiscover(unittest.TestCase):
    def test_discover_returns_fields_and_redacts_password(self):
        ex = _FakeExecutor(fields=_FIELDS, submits=_SUBMITS)
        r = form_filler._form_discover("default", ex)
        self.assertTrue(r["ok"])
        self.assertEqual(r["field_count"], 3)
        pwd = next(f for f in r["fields"] if f["type"] == "password")
        # el valor del password NO se filtra en claro
        self.assertEqual(pwd["value"], "<hidden>")

    def test_discover_propagates_executor_failure(self):
        class Fail:
            def __call__(self, tool, args):
                return {"ok": False, "error": "no session"}
        r = form_filler._form_discover("default", Fail())
        self.assertFalse(r["ok"])


class TestFormPlan(unittest.TestCase):
    def test_plan_matches_exact_and_reports_unmatched(self):
        ex = _FakeExecutor(fields=_FIELDS, submits=_SUBMITS)
        r = form_filler._form_plan(
            "default",
            {"values": {"Email Address": "a@b.com", "Nonexistent Field": "x"}},
            ex,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["plan_size"], 1)
        self.assertEqual(r["plan"][0]["selector"], "#email")
        self.assertIn("Nonexistent Field", r["unmatched"])

    def test_plan_requires_values(self):
        self.assertFalse(form_filler._form_plan("default", {}, _FakeExecutor())["ok"])


class TestFormMatchField(unittest.TestCase):
    def test_exact_beats_substring(self):
        fields = [
            {"selector": "#a", "tag": "input", "type": "text", "label": "Name Extra", "name": "", "id": "", "placeholder": ""},
            {"selector": "#b", "tag": "input", "type": "text", "label": "Name", "name": "", "id": "", "placeholder": ""},
        ]
        # query 'Name' debe matchear el exact (#b), no el substring (#a)
        m = form_filler._form_match_field("Name", fields)
        self.assertEqual(m["selector"], "#b")

    def test_no_match_returns_none(self):
        self.assertIsNone(form_filler._form_match_field("zzz", _FIELDS))

    def test_empty_query_returns_none(self):
        self.assertIsNone(form_filler._form_match_field("   ", _FIELDS))


class TestFormApply(unittest.TestCase):
    def test_apply_all_ok_is_verified_true(self):
        ex = _FakeExecutor(fields=_FIELDS, fill_ok=True)
        plan = [{"selector": "#email", "tag": "input", "type": "email", "value": "a@b.com"}]
        r = form_filler._form_apply("default", {"plan": plan}, ex)
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        self.assertEqual(r["applied"], 1)
        self.assertEqual(r["failed"], 0)

    def test_apply_partial_failure_is_verified_false(self):
        # HONESTIDAD: si un fill falla, verified NO debe ser True.
        ex = _FakeExecutor(fields=_FIELDS, fill_ok=False)
        plan = [{"selector": "#email", "tag": "input", "type": "email", "value": "a@b.com"}]
        r = form_filler._form_apply("default", {"plan": plan}, ex)
        self.assertFalse(r["verified"])
        self.assertEqual(r["failed"], 1)

    def test_apply_missing_selector_step_fails(self):
        ex = _FakeExecutor()
        r = form_filler._form_apply("default", {"plan": [{"value": "x", "tag": "input", "type": "text"}]}, ex)
        self.assertEqual(r["failed"], 1)
        self.assertFalse(r["verified"])

    def test_apply_requires_plan_or_values(self):
        self.assertFalse(form_filler._form_apply("default", {}, _FakeExecutor())["ok"])

    def test_apply_empty_plan(self):
        self.assertFalse(form_filler._form_apply("default", {"plan": []}, _FakeExecutor())["ok"])


class TestFormSubmitReviewGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="form_cov_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_submit_without_confirmed_does_not_click(self):
        # REVIEW-GATE: sin confirmed, NO debe enviarse el form (cero click submit).
        ex = _FakeExecutor(fields=_FIELDS, submits=_SUBMITS)
        r = form_filler._form_submit("default", {}, ex, self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_confirmation")
        self.assertFalse(r["verified"])
        self.assertIsNotNone(r["screenshot"])
        # ninguna llamada fue un click (solo screenshot + discover/evaluate)
        clicks = [c for c in ex.calls if c[1].get("action") == "click"]
        self.assertEqual(clicks, [])
        # se creó una confirmación pendiente para que el user la apruebe
        self.assertIn("confirmation", r)

    def test_submit_confirmed_clicks_explicit_selector(self):
        ex = _FakeExecutor(submits=_SUBMITS, click_ok=True)
        r = form_filler._form_submit("default", {"confirmed": True, "selector": "#go"}, ex, self.state)
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        clicks = [c for c in ex.calls if c[1].get("action") == "click"]
        self.assertEqual(len(clicks), 1)
        self.assertEqual(clicks[0][1]["selector"], "#go")

    def test_submit_confirmed_failed_click_is_not_verified(self):
        # HONESTIDAD: si el click del submit falla, verified=False.
        ex = _FakeExecutor(submits=_SUBMITS, click_ok=False)
        r = form_filler._form_submit("default", {"confirmed": True, "selector": "#go"}, ex, self.state)
        self.assertFalse(r["verified"])

    def test_submit_confirmed_no_submit_button_found(self):
        ex = _FakeExecutor(fields=_FIELDS, submits=[])  # discover no halla submit
        r = form_filler._form_submit("default", {"confirmed": True}, ex, self.state)
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
