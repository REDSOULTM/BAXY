"""Database domain tool — extracted from domain_tools.py.

SQLite (stdlib siempre) + Postgres (psycopg/psycopg2 opcional) + MySQL
(mysql-connector-python / pymysql opcional). Cada call pasa sus connection
params (host/port/user/password/db).

SEGURIDAD:
  - query (SELECT/WITH/EXPLAIN/PRAGMA/SHOW): driver-level read-only enforcement
    (PRAGMA query_only=1 / SET TRANSACTION READ ONLY) además de pre-check
    heurístico. CC-018 / T2-database-readonly-heuristic-018.
  - execute (mutación): hard_gate obligatorio independiente de safety_enabled.
    CC-101 / CC-019. El agente NO puede auto-confirmar.
  - schema: identifier validado contra RX_SQL_IDENT antes de interpolar en
    PRAGMA table_info(...) (sqlite/mysql). CC-017 / T2-database-schema-
    fstring-injection-017.

Funciones extraídas (10):
  database_tool                  (entry, 6 acciones)
  _database_connect              (sqlite/postgres/mysql, deps opcionales)
  _database_list_tables
  _database_schema               (per-driver SQL)
  _apply_readonly / _release_readonly
  _database_query                (con driver-level read-only)
  _database_execute              (con hard_gate)
  _database_export_csv
  _is_read_only_sql              (strip comments + prefix check)
  _scalarize                     (None/str/int/float/bool -> as-is, else str)

Helpers desde domain_tools (lazy): _hard_gate."""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from typing import Any

from .._ps import PSValidationError, RX_SQL_IDENT, ps_safe_literal
from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "database_tool",
    "_database_connect",
    "_database_list_tables",
    "_database_schema",
    "_apply_readonly",
    "_release_readonly",
    "_database_query",
    "_database_execute",
    "_database_export_csv",
    "_is_read_only_sql",
    "_scalarize",
]


def database_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local databases.

    Actions: status, list_tables, schema, query (read-only SELECT), execute
    (mutating), export_csv. Drivers: sqlite (stdlib), postgres (psycopg if
    available), mysql (mysql-connector or pymysql if available). For postgres/
    mysql, pass connection params per call (host, port, user, password, db).
    Mutating actions (execute) are not auto-checkpointed because they could
    span millions of rows; the agent must confirm explicitly.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            sqlite=True,
            psycopg=importlib.util.find_spec("psycopg") is not None or importlib.util.find_spec("psycopg2") is not None,
            mysql_connector=importlib.util.find_spec("mysql.connector") is not None,
            pymysql=importlib.util.find_spec("pymysql") is not None,
            note="SQLite is always available. Postgres needs psycopg or psycopg2; MySQL needs mysql-connector-python or pymysql.",
        )
    driver = str(args.get("driver") or "sqlite").casefold()
    try:
        conn, cleanup = _database_connect(driver, args)
    except Exception as exc:
        return _err(f"connect failed: {exc}", driver=driver)
    try:
        if action == "list_tables":
            return _database_list_tables(conn, driver)
        if action == "schema":
            return _database_schema(conn, driver, args)
        if action == "query":
            return _database_query(conn, driver, args)
        if action == "execute":
            return _database_execute(conn, driver, args, state)
        if action == "export_csv":
            return _database_export_csv(conn, driver, args, state)
        return _err(
            "unknown database action", action=action,
            valid_actions=["status", "list_tables", "schema", "query"],
            status="needs_user",
        )
    finally:
        cleanup()


def _database_connect(driver: str, args: dict[str, Any]):
    if driver == "sqlite":
        import sqlite3
        path_raw = str(args.get("path") or args.get("database") or "").strip()
        if not path_raw:
            return None, lambda: None
        path = Path(path_raw).expanduser()
        if not path.is_file() and not bool(args.get("create", False)):
            raise FileNotFoundError(f"SQLite file not found: {path} (pass create=true to allow creating)")
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn, conn.close
    if driver == "postgres":
        if importlib.util.find_spec("psycopg") is not None:
            import psycopg  # type: ignore[import-not-found]
            conn = psycopg.connect(
                host=args.get("host", "localhost"),
                port=int(args.get("port", 5432)),
                user=args.get("user"),
                password=args.get("password"),
                dbname=args.get("database") or args.get("db"),
            )
        elif importlib.util.find_spec("psycopg2") is not None:
            import psycopg2  # type: ignore[import-not-found]
            import psycopg2.extras  # type: ignore[import-not-found]
            conn = psycopg2.connect(
                host=args.get("host", "localhost"),
                port=int(args.get("port", 5432)),
                user=args.get("user"),
                password=args.get("password"),
                dbname=args.get("database") or args.get("db"),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        else:
            raise RuntimeError("neither psycopg nor psycopg2 is installed")
        return conn, conn.close
    if driver == "mysql":
        host = str(args.get("host") or "localhost")
        port = int(args.get("port") or 3306)
        user = str(args.get("user") or "")
        password = str(args.get("password") or "")
        database = str(args.get("database") or args.get("db") or "")
        if importlib.util.find_spec("mysql.connector") is not None:
            import mysql.connector  # type: ignore[import-not-found]
            conn = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
            )
        elif importlib.util.find_spec("pymysql") is not None:
            import pymysql  # type: ignore[import-not-found]
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                cursorclass=pymysql.cursors.DictCursor,
            )
        else:
            raise RuntimeError("neither mysql-connector-python nor pymysql is installed")
        return conn, conn.close
    raise RuntimeError(f"unsupported driver: {driver}")


def _database_list_tables(conn: Any, driver: str) -> dict[str, Any]:
    cur = conn.cursor()
    if driver == "sqlite":
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
    elif driver == "postgres":
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_name")
    else:  # mysql
        cur.execute("SHOW TABLES")
    rows = cur.fetchall()
    tables: list[str] = []
    for row in rows:
        if hasattr(row, "keys"):
            values = list(row.values()) if hasattr(row, "values") else list(dict(row).values())
            if values:
                tables.append(str(values[0]))
        elif isinstance(row, (list, tuple)) and row:
            tables.append(str(row[0]))
    return _ok(driver=driver, tables=tables, count=len(tables))


def _database_schema(conn: Any, driver: str, args: dict[str, Any]) -> dict[str, Any]:
    table_raw = str(args.get("table") or "").strip()
    if not table_raw:
        return _err("missing table name")
    # CC-017 / T2-database-schema-fstring-injection-017: validar identifier.
    try:
        table = ps_safe_literal(table_raw, RX_SQL_IDENT)
    except PSValidationError:
        return _err(
            "invalid table identifier (allowed: letters/digits/underscore, optional schema.table)",
            table=table_raw,
            status="needs_user",
        )
    cur = conn.cursor()
    if driver == "sqlite":
        cur.execute(f"PRAGMA table_info({table})")
        columns = [{"name": r[1], "type": r[2], "notnull": bool(r[3]), "default": r[4], "pk": bool(r[5])} for r in cur.fetchall()]
    elif driver == "postgres":
        cur.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
        columns = [{"name": r[0] if isinstance(r, (list, tuple)) else r["column_name"], "type": r[1] if isinstance(r, (list, tuple)) else r["data_type"]} for r in cur.fetchall()]
    else:
        cur.execute(f"DESCRIBE {table}")
        columns = [{"name": (r[0] if isinstance(r, (list, tuple)) else r.get("Field")), "type": (r[1] if isinstance(r, (list, tuple)) else r.get("Type"))} for r in cur.fetchall()]
    return _ok(driver=driver, table=table, columns=columns)


def _apply_readonly(conn: Any, driver: str) -> None:
    """CC-018: aplica read-only a nivel de driver para la duración del query.
    SQLite -> PRAGMA query_only=1
    Postgres -> SET TRANSACTION READ ONLY (en transacción explícita)
    MySQL -> SET SESSION TRANSACTION READ ONLY
    Si el driver no soporta la operación, la silenciamos (best-effort).
    """
    cur = conn.cursor()
    try:
        if driver == "sqlite":
            cur.execute("PRAGMA query_only = 1")
        elif driver == "postgres":
            cur.execute("BEGIN")
            cur.execute("SET TRANSACTION READ ONLY")
        elif driver == "mysql":
            cur.execute("SET SESSION TRANSACTION READ ONLY")
    except Exception:
        pass


def _release_readonly(conn: Any, driver: str) -> None:
    cur = conn.cursor()
    try:
        if driver == "sqlite":
            cur.execute("PRAGMA query_only = 0")
        elif driver == "postgres":
            try:
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        elif driver == "mysql":
            cur.execute("SET SESSION TRANSACTION READ WRITE")
    except Exception:
        pass


def _database_query(conn: Any, driver: str, args: dict[str, Any]) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql:
        return _err("missing sql")
    # Pre-check informativo; el enforcement real es a nivel de driver.
    if not _is_read_only_sql(sql):
        return _err(
            "query is restricted to read-only statements (SELECT, WITH, EXPLAIN, PRAGMA, SHOW). Use execute(...) for mutations.",
            status="needs_user",
        )
    # CC-018 / T2-database-readonly-heuristic-018: driver-level enforcement.
    _apply_readonly(conn, driver)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        try:
            rows = cur.fetchall()
        except Exception:
            rows = []
        columns = [d[0] for d in cur.description] if cur.description else []
        serialized: list[dict[str, Any]] = []
        for row in rows[: int(args.get("limit", 200))]:
            if isinstance(row, dict):
                serialized.append({k: _scalarize(v) for k, v in row.items()})
            elif hasattr(row, "keys"):
                serialized.append({k: _scalarize(row[k]) for k in row.keys()})
            else:
                serialized.append({columns[i] if i < len(columns) else f"col{i}": _scalarize(v) for i, v in enumerate(row)})
        return _ok(sql=sql, columns=columns, row_count=len(rows), rows=serialized)
    finally:
        _release_readonly(conn, driver)


def _database_execute(conn: Any, driver: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .._shared import hard_gate as _hard_gate
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql:
        return _err("missing sql")
    if _is_read_only_sql(sql):
        return _err("execute is for mutations; use query(...) for SELECT")
    # CC-101 / CC-019: gate duro independiente de safety_enabled.
    gate = _hard_gate(
        state,
        tool="database",
        action="execute",
        args=args,
        reason=f"database.execute will mutate the database: {sql[:200]}",
        risk="high",
    )
    if gate is not None:
        return gate
    cur = conn.cursor()
    cur.execute(sql)
    # El commit DEBE confirmar la durabilidad. Tragar su excepcion y reportar
    # verified=True igual seria mentir sobre una mutacion no persistida (DB bloqueada,
    # disco lleno, constraint diferido): es el anti-patron "claim verified pese a que
    # el paso de persistencia fallo", y database.execute es high-risk + destructivo.
    rowcount = cur.rowcount if hasattr(cur, "rowcount") else None
    try:
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return _err(
            f"la mutacion se ejecuto pero el commit fallo: {exc}",
            status="failed", reason="commit_failed", sql=sql, driver=driver,
            rowcount=rowcount, verified=False,
        )
    return _ok(sql=sql, driver=driver, rowcount=rowcount, verified=True)


def _database_export_csv(conn: Any, driver: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    sql = str(args.get("sql") or args.get("query") or "").strip()
    if not sql or not _is_read_only_sql(sql):
        return _err("export_csv requires a read-only SQL query")
    dst_raw = str(args.get("dst") or args.get("output") or "").strip()
    if dst_raw:
        dst = Path(dst_raw).expanduser()
    else:
        dst = state.path.parent / "database_exports" / f"export_{int(time.time())}.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    _apply_readonly(conn, driver)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        import csv
        with dst.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow([_scalarize(row.get(c)) for c in columns])
                elif hasattr(row, "keys"):
                    writer.writerow([_scalarize(row[c]) for c in columns])
                else:
                    writer.writerow([_scalarize(v) for v in row])
        return _ok(sql=sql, driver=driver, dst=str(dst), rows=len(rows), verified=dst.is_file())
    finally:
        _release_readonly(conn, driver)


def _is_read_only_sql(sql: str) -> bool:
    s = sql.strip().casefold()
    # Strip leading comments and whitespace.
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            s = s.split("\n", 1)[1].strip() if "\n" in s else ""
        else:
            end = s.find("*/")
            s = s[end + 2:].strip() if end >= 0 else ""
    return s.startswith(("select", "with", "explain", "pragma", "show", "describe"))


def _scalarize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
