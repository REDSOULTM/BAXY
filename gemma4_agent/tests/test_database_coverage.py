"""Cobertura dedicada para domain_tools/database.py (added 2026-06-01).

database.py NO tenía test propio (solo el smoke {action:status}). Usa SQLite
(stdlib, siempre disponible) -> los tests corren contra una BD REAL en tmp, sin
mocks, lo que da máxima fidelidad. Postgres/MySQL no se tocan (deps opcionales).

El contrato CRÍTICO son tres guardas de seguridad declaradas en el docstring:
  - CC-018: query() es read-only enforced a nivel de driver (PRAGMA query_only=1)
    además del pre-check heurístico. Una mutación enviada a query() se RECHAZA.
  - CC-101/CC-019: execute() (mutación) exige hard_gate (confirmed) SIEMPRE,
    independiente de safety_enabled. El agente NO puede auto-confirmar.
  - CC-017: schema() valida el identifier de tabla contra RX_SQL_IDENT antes de
    interpolarlo en PRAGMA table_info(...) (f-string injection).

Propiedades afirmadas contra el código fuente:
  - query SELECT real devuelve filas serializadas
  - query con mutación (UPDATE/DELETE) -> needs_user, la fila NO cambia
  - PRAGMA query_only realmente bloquea un UPDATE colado en query()
  - execute sin confirmed -> gate (no muta); con confirmed -> muta y verified True
  - schema con identifier inyectable -> needs_user, sin tocar la BD
  - _is_read_only_sql ignora comentarios líder (no se puede esconder un DELETE)
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ..domain_tools import database
from ..memory_pkg.state import AgentState


def _make_db(path: Path):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    conn.execute("INSERT INTO users (name, age) VALUES ('alice', 30), ('bob', 25)")
    conn.commit()
    conn.close()


class TestDatabaseStatus(unittest.TestCase):
    def test_status_reports_drivers(self):
        r = database.database_tool({"action": "status"}, None)
        self.assertTrue(r["ok"])
        self.assertTrue(r["sqlite"])  # stdlib siempre
        for key in ("psycopg", "mysql_connector", "pymysql"):
            self.assertIn(key, r)
            self.assertIsInstance(r[key], bool)


class TestDatabaseReadOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="db_cov_"))
        self.db = self.tmp / "t.sqlite"
        _make_db(self.db)
        self.state = AgentState(self.tmp / "s.json")

    def test_select_returns_rows(self):
        r = database.database_tool(
            {"action": "query", "driver": "sqlite", "path": str(self.db),
             "sql": "SELECT name, age FROM users ORDER BY age"},
            self.state,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["row_count"], 2)
        self.assertEqual(r["rows"][0]["name"], "bob")
        self.assertEqual(r["rows"][1]["name"], "alice")

    def test_mutation_in_query_rejected_by_precheck(self):
        # CC-018 pre-check: UPDATE enviado a query() -> needs_user, sin ejecutar.
        r = database.database_tool(
            {"action": "query", "driver": "sqlite", "path": str(self.db),
             "sql": "UPDATE users SET age = 99"},
            self.state,
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        # la fila NO cambió
        conn = sqlite3.connect(str(self.db))
        ages = [row[0] for row in conn.execute("SELECT age FROM users")]
        conn.close()
        self.assertNotIn(99, ages)

    def test_query_only_pragma_blocks_smuggled_mutation(self):
        # Defensa en profundidad CC-018: aunque el heurístico fallara, el driver
        # está en query_only=1. Comprobamos que el enforcement de driver realmente
        # bloquea una escritura. Llamamos _database_query directo con un UPDATE que
        # empieza con un comentario que igual el precheck atrapa; para aislar el
        # PRAGMA usamos un statement que el precheck deja pasar como read-only
        # ('WITH ...') pero que intenta escribir vía un sub-statement no es posible
        # en sqlite; así que verificamos el PRAGMA de forma directa.
        conn = sqlite3.connect(str(self.db))
        database._apply_readonly(conn, "sqlite")
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("UPDATE users SET age = 1")
        database._release_readonly(conn, "sqlite")
        # tras release, la escritura vuelve a permitirse (no dejamos la conn rota)
        conn.execute("UPDATE users SET age = age")  # no-op pero permitido
        conn.close()

    def test_list_tables_real(self):
        r = database.database_tool(
            {"action": "list_tables", "driver": "sqlite", "path": str(self.db)},
            self.state,
        )
        self.assertTrue(r["ok"])
        self.assertIn("users", r["tables"])


class TestDatabaseExecuteGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="db_exec_"))
        self.db = self.tmp / "t.sqlite"
        _make_db(self.db)
        self.state = AgentState(self.tmp / "s.json")

    def test_execute_without_confirmed_is_gated_and_does_not_mutate(self):
        # CC-101/CC-019: la mutación exige confirmación; sin ella NO debe ejecutarse.
        r = database.database_tool(
            {"action": "execute", "driver": "sqlite", "path": str(self.db),
             "sql": "DELETE FROM users"},
            self.state,
        )
        self.assertFalse(r["ok"])
        # la tabla sigue intacta
        conn = sqlite3.connect(str(self.db))
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        self.assertEqual(n, 2)

    def test_execute_with_confirmed_mutates_and_verifies(self):
        r = database.database_tool(
            {"action": "execute", "driver": "sqlite", "path": str(self.db),
             "sql": "DELETE FROM users WHERE age < 28", "confirmed": True},
            self.state,
        )
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"])
        conn = sqlite3.connect(str(self.db))
        names = [row[0] for row in conn.execute("SELECT name FROM users")]
        conn.close()
        self.assertEqual(names, ["alice"])  # bob (25) borrado

    def test_execute_rejects_select(self):
        # execute es para mutaciones; un SELECT debe rebotar a query().
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        r = database._database_execute(conn, "sqlite", {"sql": "SELECT 1"}, self.state)
        conn.close()
        self.assertFalse(r["ok"])


class TestDatabaseSchemaInjection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="db_schema_"))
        self.db = self.tmp / "t.sqlite"
        _make_db(self.db)
        self.state = AgentState(self.tmp / "s.json")

    def test_schema_valid_table(self):
        r = database.database_tool(
            {"action": "schema", "driver": "sqlite", "path": str(self.db), "table": "users"},
            self.state,
        )
        self.assertTrue(r["ok"])
        names = {c["name"] for c in r["columns"]}
        self.assertEqual(names, {"id", "name", "age"})

    def test_schema_injection_identifier_rejected(self):
        # CC-017: un identifier con paréntesis/punto-y-coma (inyección f-string en
        # PRAGMA table_info(...)) debe rechazarse SIN tocar la BD.
        r = database.database_tool(
            {"action": "schema", "driver": "sqlite", "path": str(self.db),
             "table": "users); DROP TABLE users;--"},
            self.state,
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_user")
        # la tabla sigue existiendo (no se ejecutó el DROP)
        conn = sqlite3.connect(str(self.db))
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        conn.close()
        self.assertIn("users", tables)


class TestIsReadOnlySql(unittest.TestCase):
    def test_select_with_and_explain_are_readonly(self):
        for sql in ("SELECT 1", "  with x as (select 1) select * from x",
                    "EXPLAIN SELECT 1", "PRAGMA table_info(users)", "SHOW TABLES"):
            self.assertTrue(database._is_read_only_sql(sql), sql)

    def test_mutations_are_not_readonly(self):
        for sql in ("UPDATE t SET a=1", "DELETE FROM t", "INSERT INTO t VALUES (1)",
                    "DROP TABLE t", "ALTER TABLE t ADD c INT"):
            self.assertFalse(database._is_read_only_sql(sql), sql)

    def test_leading_comment_cannot_hide_mutation(self):
        # Un comentario líder NO debe poder camuflar un DELETE como read-only.
        self.assertFalse(database._is_read_only_sql("-- harmless\nDELETE FROM t"))
        self.assertFalse(database._is_read_only_sql("/* c */ DROP TABLE t"))

    def test_leading_comment_before_select_still_readonly(self):
        self.assertTrue(database._is_read_only_sql("-- comment\nSELECT 1"))


if __name__ == "__main__":
    unittest.main()
