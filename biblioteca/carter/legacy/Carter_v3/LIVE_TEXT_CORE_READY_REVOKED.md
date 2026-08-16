# LIVE_TEXT_CORE_READY_REVOKED

Fecha: 2026-05-05

- El veredicto `LIVE_TEXT_CORE_READY` del Cycle 5 queda **revocado**.
- Razón: `FINAL_LIVE_READY_AUDIT.md` detectó que el harness de smoke (`audit/smoke_live_cycle_5.py`) era demasiado permisivo para declarar cierre real.
- El estado correcto vuelve a ser `LIVE_TEXT_CORE_ALMOST_READY` o `LIVE_TEXT_CORE_NOT_READY` hasta repetir smoke estricto con oráculos confiables.
- El commit `76c10510` no debe considerarse cierre final del runtime.
- No se revierten necesariamente los fixes de código runtime; se revierte únicamente la confianza en el veredicto de cierre.

## Alcance de esta revocación

- Sí: revocación de confianza del resultado de auditoría Cycle 5.
- No: rollback automático de cambios de runtime.
- Sí: obligación de re-ejecutar smoke live con harness estricto antes de cualquier nuevo veredicto de readiness.
