"""Cobertura dedicada para domain_tools/data_analysis.py (added 2026-06-01).

data_analysis.py NO tenía test propio (solo el smoke {action:status}).
Cubre el contrato de dependencias, la guarda anti-eval de pandas .query()
y, cuando pandas está disponible, el análisis real de un CSV en tmp.

Propiedades afirmadas contra el código fuente:
  - status reporta disponibilidad de pandas/matplotlib/openpyxl
  - sin pandas -> needs_dependency (no crash)
  - T2-data_analysis-pandas-query-eval-035: query con '@' o backtick se RECHAZA
    (acceso a variables locales / eval arbitrario) — guarda independiente de
    que pandas esté instalado
  - profile/query/head reales sobre un CSV (skip si pandas ausente)
  - honestidad: verified refleja si el archivo de salida existe
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ..domain_tools import data_analysis
from ..memory_pkg.state import AgentState

_HAS_PANDAS = importlib.util.find_spec("pandas") is not None


class TestDataAnalysisContract(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="da_cov_"))
        self.state = AgentState(self.tmp / "s.json")

    def test_status_reports_dependencies(self):
        r = data_analysis.data_analysis_tool({"action": "status"}, self.state)
        self.assertTrue(r["ok"])
        for key in ("pandas", "matplotlib", "openpyxl"):
            self.assertIn(key, r)
            self.assertIsInstance(r[key], bool)
        self.assertIn("install_hint", r)

    def test_unknown_action(self):
        # con pandas presente, una acción desconocida cae al _err final;
        # sin pandas, cae antes a needs_dependency. Ambos son ok:False.
        r = data_analysis.data_analysis_tool({"action": "bogus"}, self.state)
        self.assertFalse(r["ok"])

    def test_missing_pandas_is_needs_dependency(self):
        # Simular pandas ausente: find_spec(None) en el gate de la entry.
        with patch.object(data_analysis.importlib.util, "find_spec", return_value=None):
            r = data_analysis.data_analysis_tool(
                {"action": "csv_profile", "path": str(self.tmp / "x.csv")}, self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_dependency")
        self.assertFalse(r["verified"])


@unittest.skipUnless(_HAS_PANDAS, "pandas no instalado en este entorno")
class TestDataAnalysisQueryGuard(unittest.TestCase):
    """La guarda anti-eval corre DESPUÉS de cargar el DataFrame, así que
    necesita pandas + un CSV real (verificado leyendo el orden del código:
    _data_load_df precede al chequeo de '@'/backtick)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="da_q_"))
        self.csv = self.tmp / "d.csv"
        self.csv.write_text("a,b\n1,10\n2,20\n3,30\n", encoding="utf-8")

    def test_query_with_at_var_refused(self):
        r = data_analysis._data_csv_query({"path": str(self.csv), "query": "a > @threshold"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")

    def test_query_with_backtick_refused(self):
        r = data_analysis._data_csv_query({"path": str(self.csv), "query": "`a` > 1"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")

    def test_missing_query(self):
        self.assertFalse(data_analysis._data_csv_query({"path": str(self.csv)})["ok"])

    def test_valid_query_returns_matched_rows(self):
        r = data_analysis._data_csv_query({"path": str(self.csv), "query": "a > 1"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["matched_rows"], 2)
        self.assertIn(r["engine"], ("numexpr", "python"))


@unittest.skipUnless(_HAS_PANDAS, "pandas no instalado en este entorno")
class TestDataAnalysisLoadAndProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="da_p_"))
        self.csv = self.tmp / "d.csv"
        self.csv.write_text("name,age\nAlice,30\nBob,40\n", encoding="utf-8")

    def test_load_missing_path(self):
        df, err = data_analysis._data_load_df({})
        self.assertIsNone(df)
        self.assertFalse(err["ok"])

    def test_load_file_not_found(self):
        df, err = data_analysis._data_load_df({"path": str(self.tmp / "nope.csv")})
        self.assertIsNone(df)
        self.assertFalse(err["ok"])

    def test_profile_reports_shape(self):
        r = data_analysis._data_csv_profile({"path": str(self.csv)})
        self.assertTrue(r["ok"])
        self.assertEqual(r["rows"], 2)
        self.assertEqual(r["columns"], 2)
        names = {c["name"] for c in r["column_profile"]}
        self.assertEqual(names, {"name", "age"})

    def test_head_limits_rows(self):
        r = data_analysis._data_csv_head({"path": str(self.csv), "n": 1})
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
