# Logs archivados — corte 2026-06-03

Respaldo de los logs de runtime acumulados **hasta el 2026-06-03**, archivados antes
de reiniciar el logging desde cero. Así, al correr la app desde esta fecha, los
errores nuevos no se mezclan con los de sesiones viejas.

`logs_runtime_hasta_2026-06-03.zip` contiene (41 archivos, ~7.7 MB):
- `gemma4_home_logs/` — `~/.gemma4/logs/` (chat.log, full.log, crash.log por sesión).
- `repo_logs/` — `gemma4_agent/logs/` (logs del paquete).
- `traces.jsonl` — el trace de turnos del agente.

**NO incluye** `~/.gemma4/behavior/` (la capa Jarvis de perfil de gustos, que sigue
viva y activa — no es un log de errores).

Es archivo histórico para diagnóstico retrospectivo; no refleja el estado actual.
