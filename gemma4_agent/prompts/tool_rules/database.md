Database rule: database(...) queries SQLite / Postgres / MySQL. Actions: status, list_tables, schema, query, execute, export_csv.

query is restricted to read-only SELECT statements; mutations go through execute. SQLite uses stdlib; Postgres needs psycopg or psycopg2; MySQL needs mysql-connector-python or pymysql — returns needs_dependency if absent.

Distinct from data_analysis(...) (pandas on CSVs, no SQL engine) and from filesystem(...) (no schema awareness). Always cite the table/row counts returned by the tool in your reply rather than estimating.
