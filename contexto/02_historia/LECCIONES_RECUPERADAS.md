# Lecciones recuperadas

Estado: **36 modos estructurales especificados; 0 cerrados sobre el producto
nuevo**. Matriz completa: `documentacion/05_FALLOS_Y_REGRESIONES.md`.

## Invariantes que BAXY 1.0 debe demostrar

- Efecto observado, no dispatch/stub/clic (`R-001`, `R-009`, `R-035`).
- Identidad completa de runtime, app y target (`R-002`, `R-031`, `R-036`).
- Readiness honesto y perfiles incompatibles (`R-003`, `R-027`).
- Operaciones componibles y router evaluado en logs reales (`R-004`–`R-008`).
- Riesgo proporcional, protección de trabajo y costo (`R-011`–`R-013`).
- Deadlines por fase, cleanup e idempotencia (`R-010`, `R-014`–`R-016`).
- Unicode/NUL/locale y memoria privada/controlable (`R-017`, `R-018`, `R-033`).
- Voz física: no fake-wake, entidades, AEC/barge-in y coherencia TTS/GUI
  (`R-019`–`R-022`).
- Percepción corroborada y shell recuperable (`R-023`, `R-024`).
- Recursos y distribución medidos honestamente (`R-025`, `R-026`).
- Conversación natural, orden correcto de gates y artefactos inmutables
  (`R-028`–`R-030`).
- Dependencias externas y forma pragmática sin claims inventados
  (`R-032`, `R-034`, `R-035`).

Las 117 ocurrencias de feedback/fallo permanecen individualmente enlazadas en
el corpus. La generalización en 36 regresiones no borra su procedencia.
