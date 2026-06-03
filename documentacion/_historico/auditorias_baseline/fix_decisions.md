# Fix Decisions — Carter Agent
Decisiones tomadas autónomamente durante la sesión (regla conservadora: menos código, sin nuevas deps, sin cambio de firmas públicas).

---

## Drivers SQL detectados (CC-018)
- contexto: T2-database-readonly-heuristic-018 — `_database_connect` en `domain_tools.py:1685`
- detectado: **sqlite (stdlib)**, **psycopg / psycopg2** (opcionales), **mysql.connector / pymysql** (opcionales)
- elegido: aplicar `PRAGMA query_only=1/0` para SQLite, `SET TRANSACTION READ ONLY` para Postgres, `SET SESSION TRANSACTION READ ONLY/WRITE` para MySQL — todos en try/finally
- alternativa: usar sqlglot u otro parser; descartada por instrucción explícita ("NO usar sqlglot") y "no nuevas deps"
- razón: el procedimiento del prompt lo cubre y no introduce nuevas dependencias

