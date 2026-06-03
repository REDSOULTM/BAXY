Database: database(...) consulta SQLite/Postgres/MySQL. Actions: status, list_tables, schema, query, execute, export_csv.

- query = SOLO SELECT read-only; mutaciones van por execute.
- SQLite=stdlib; Postgres=psycopg/psycopg2; MySQL=mysql-connector-python/pymysql -> si falta, devuelve needs_dependency.

Distinto de data_analysis(...) (pandas sobre CSV, sin motor SQL) y filesystem(...) (sin schema). Citá SIEMPRE los counts de tablas/filas que devuelve el tool, NO los estimes.
