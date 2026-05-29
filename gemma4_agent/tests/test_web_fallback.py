"""B7 (competidores): web search con fallback dual (DDG -> Bing). Tests de la LÓGICA
de fallback con motores mockeados (sin red). La validación EN VIVO (que el regex de
Bing matchee el HTML real) es batcheada — es segura igual: si Bing no matchea -> []
-> mismo "en blanco" que hoy, sin regresión.
"""
import os
import unittest

from ..tools_pkg import tools as T


class _Patch:
    """Monkeypatch DDG/Bing + el flag, restaurando al salir."""
    def __init__(self, ddg, bing, fallback=True):
        self.ddg, self.bing, self.fallback = ddg, bing, fallback
        self._saved = {}

    def __enter__(self):
        self._saved["ddg"] = T._duckduckgo_search
        self._saved["bing"] = T._bing_search
        self._saved["env"] = os.environ.get("GEMMA4_WEB_FALLBACK")
        T._duckduckgo_search = self.ddg
        T._bing_search = self.bing
        os.environ["GEMMA4_WEB_FALLBACK"] = "1" if self.fallback else "0"
        return self

    def __exit__(self, *exc):
        T._duckduckgo_search = self._saved["ddg"]
        T._bing_search = self._saved["bing"]
        if self._saved["env"] is None:
            os.environ.pop("GEMMA4_WEB_FALLBACK", None)
        else:
            os.environ["GEMMA4_WEB_FALLBACK"] = self._saved["env"]


_DDG = [{"title": "ddg", "url": "http://d"}]
_BING = [{"title": "bing", "url": "http://b"}]


def _raise(*a, **k):
    raise RuntimeError("ddg down")


class TestWebFallback(unittest.TestCase):
    def test_ddg_ok_does_not_use_bing(self):
        bing_called = []
        with _Patch(ddg=lambda q, limit=6: _DDG,
                    bing=lambda q, limit=6: bing_called.append(1) or _BING):
            name, res = T._web_search_provider("x")
        self.assertEqual(res, _DDG)
        self.assertEqual(name, "duckduckgo_html")
        self.assertEqual(bing_called, [])  # Bing NO se llamó

    def test_ddg_empty_falls_back_to_bing(self):
        with _Patch(ddg=lambda q, limit=6: [], bing=lambda q, limit=6: _BING):
            name, res = T._web_search_provider("x")
        self.assertEqual(res, _BING)
        self.assertEqual(name, "bing_html_fallback")

    def test_ddg_raises_falls_back_to_bing(self):
        with _Patch(ddg=_raise, bing=lambda q, limit=6: _BING):
            name, res = T._web_search_provider("x")
        self.assertEqual(res, _BING)

    def test_both_empty_returns_empty(self):
        with _Patch(ddg=lambda q, limit=6: [], bing=lambda q, limit=6: []):
            name, res = T._web_search_provider("x")
        self.assertEqual(res, [])

    def test_bing_raises_is_swallowed(self):
        with _Patch(ddg=lambda q, limit=6: [], bing=_raise):
            name, res = T._web_search_provider("x")
        self.assertEqual(res, [])  # no crash

    def test_gate_off_is_original_behavior(self):
        # con el flag OFF, NUNCA toca Bing aunque DDG venga vacío (comportamiento original)
        bing_called = []
        with _Patch(ddg=lambda q, limit=6: [],
                    bing=lambda q, limit=6: bing_called.append(1) or _BING, fallback=False):
            name, res = T._web_search_provider("x")
        self.assertEqual(res, [])
        self.assertEqual(bing_called, [])

    def test_gate_helper(self):
        prev = os.environ.get("GEMMA4_WEB_FALLBACK")
        try:
            os.environ.pop("GEMMA4_WEB_FALLBACK", None)
            self.assertFalse(T._web_fallback_enabled())
            os.environ["GEMMA4_WEB_FALLBACK"] = "1"
            self.assertTrue(T._web_fallback_enabled())
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_WEB_FALLBACK", None)
            else:
                os.environ["GEMMA4_WEB_FALLBACK"] = prev


if __name__ == "__main__":
    unittest.main()
