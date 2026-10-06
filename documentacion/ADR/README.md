# ADR

Cada decisión material registrará contexto, alternativas, evidencia, decisión,
consecuencias, fallback y criterio de reapertura. Las contradicciones no se
borran: se conservan como alternativas medidas o decisiones sustituidas.

| ADR | Estado | Decisión |
|---|---|---|
| `ADR-0001-arquitectura-base-baxy-1.md` | Aceptado | Shell .NET 10 WPF + core .NET NativeAOT; WPF + Rust estático como fallback Pareto |
| `ADR-0002-estado-gpu-local.md` | Aceptado | `system.status` GPU con identidad DXGI, uso puntual PDH, evidencia parcial explícita y cero subprocess |
| `ADR-0003-paquete-release-reproducible.md` | Aceptado | Release desde snapshot Git, core NativeAOT `/Brepro` y ZIP Stored canónico con checksum |
| `ADR-0004-setup-embebido-transaccional.md` | Aceptado | Setup NativeAOT con ZIP atestado, raíz canónica por usuario, versiones inmutables, journal y recovery |
- [ADR-0005 — Mente: modelos y runtime](ADR-0005-mente-modelos-y-runtime.md)
- [ADR-0006 — Planner híbrido, acotado y durable](ADR-0006-planner-hibrido-durable.md)
- [ADR-0007 — Voz local, wake verificable y salida cancelable](ADR-0007-voz-local-wake-stt-tts.md)
- [ADR-0008 — Restauración literal de BAXY Field](ADR-0008-restauracion-field-ui-historica.md)
- [ADR-0009 — Evidencia recuperada del corpus para turnos](ADR-0009-evidencia-corpus-turnos.md)
