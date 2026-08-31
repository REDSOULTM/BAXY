# Handoff — Goal 10.3 uso real A — 2026-08-31 — preparación (0/50)

## Objetivo
Cerrar el primer bloque limpio de 50 turnos reales: 25 pedidos espontáneos del dueño y cinco repeticiones de cada familia congelada. Esta sesión no lo cierra.

## Estado
Hecho: preflight técnico 10.3; causa del hijack de arranque (`memory_recovery_pending` tragaba el primer turno y `cancelar` no retiraba el outbox) corregida en App; regresión dueño verde dos veces; evidencia privada de la tanda fallida ignorada por git.
En curso: Goal 10.3. Contador **0/50**. Cero espontáneos del dueño. Cero repeticiones de familia contadas.
Sin empezar: las 25 interacciones espontáneas del dueño; las 25 repeticiones (5× `conversation`, `media.play`, `audio.volume`, `system.status`, `system.settings`); cierre 10.3; `10.4_USO_REAL_B.md`.

## Decisiones tomadas
- 0/50 se declara, no se finge. La regla de la dosis prohíbe guionizar los 25 espontáneos o sustituirlos por corpus. Sin el dueño no hay bloque.
- El lote vivo de arranque quedó como evidencia fallida, no como parte de los 50. Reinicio del bloque desde 0 tras el arreglo.
- No se repite la prueba viva de cancelación: dos sesiones se atascaron ahí. La prueba dueño `RecoveredPersistentMemoryCanBeCancelledWithoutExecuting` cubre el defecto.
- `ContinueCancel` ya existía; no se añade un array gemelo. Cancelar recovery que no puede retirarse usa `cannot_withdraw_pending`, igual que la confirmación hermana.
- Mute del endpoint Realtek no es `FALLO_DE_AMBIENTE`: pycaw lee scalar=1.0. El JSON original mintió `FALLO_DE_AMBIENTE` por un `Read` COM de PowerShell; revalidado.
- `artifacts/goal10/private/` queda gitignored. `owner-tests-1.log` / `2.log` siguen siendo la evidencia 10.2 (commit `b12f64e`).

## Archivos tocados
- `src/Baxy.App/MainWindowViewModel.cs` — `HandlePendingMemoryOperationAsync` acepta `cancelar` y vacía el outbox
- `src/Baxy.App/PrivateOperationNarration.cs` — recovery ofrece continuar/cancelar
- `src/Baxy.App/TurnVisibleFacts.cs` — sin array duplicado
- `tests/Baxy.Integration.Tests/MemoryAppFlowTests.cs` — `RecoveredPersistentMemoryCanBeCancelledWithoutExecuting`
- `.gitignore` — `/artifacts/goal10/private/`
- `artifacts/goal10/preflight-10.3.md` + `.json` — preflight + revalidación pycaw
- `artifacts/goal10/owner-tests-10.3-1.log` + `-2.log`

## Archivos relevantes aún sin tocar
- `%LOCALAPPDATA%\BAXY\dev-mente-v2\shell\retry-outbox.v1.json` — 1 entrada `memory.forget` (no versionada)
- `documentacion/sprints/10.3_USO_REAL_A.md` — criterios de cierre siguen abiertos
- `documentacion/sprints/10.4_USO_REAL_B.md` — no abrir

## Hipótesis
Confirmadas: recovery persistente al arrancar interceptaba conversación y no se podía cancelar → tests dueño 3/3 dos veces; lote fallido `artifacts/goal10/private/failed-batches/10.3-batch0-launch1-memory-recovery-hijack.jsonl`.
Descartadas: inventar 50 turnos; prueba viva de cancelación; `FALLO_DE_AMBIENTE` por mute o por el `Read` de PowerShell; avanzar a 10.4.

## Comandos ejecutados y resultado
- `dotnet test tests\Baxy.Integration.Tests -c Release --filter "FullyQualifiedName~MemoryAppFlowTests.RecoveredPersistentMemory|FullyQualifiedName~MemoryAppFlowTests.ViewModelRecovery|FullyQualifiedName~MemoryAppFlowTests.ReconciliationChallenge" --nologo -v:minimal` → `3 passed, 0 fail, 0 skip` dos veces (41 s / 40 s)
- pycaw `GetSpeakers().EndpointVolume` → device `Altavoces (Realtek(R) Audio)`, scalar 1.0, muted true
- No ejecutado: Full; soak; 50 turnos reales; prueba viva de cancelación; `10.4`

## Problemas pendientes
- 25 espontáneos del dueño — sin ellos el bloque no arranca.
- Outbox leftover `memory.forget` en `dev-mente-v2`: el próximo `py main.py` ofrecerá recovery. `cancelar` es preparación, no turno 1.
- `status.v1.json` de 22:46Z puede estar stale; no reutilizar esa sesión para los 50.
- Endpoint de salida muteado; no bloquea `audio.volume`, pero hay que tenerlo en cuenta al verificar playback.

## Siguiente acción recomendada
Misma meta `documentacion/sprints/10.3_USO_REAL_A.md`, receta abajo. No pegar `10.4`. No relanzar el fichero. No inventar espontáneos.

### Receta exacta para continuar
1. Sesión nueva, **sin** `/goal` nuevo y **sin** pegar `10.4_USO_REAL_B.md`. Continuar 10.3 desde este handoff.
2. No repetir la prueba viva de cancelación. No guionizar los 25 espontáneos. No copiar corpus.
3. El dueño aporta 25 pedidos espontáneos reales (ES/EN/spanglish). Hasta que existan, el contador sigue 0/50.
4. Arranque de campaña: `py main.py` (Release `Baxy.exe`), data root `%LOCALAPPDATA%\BAXY\dev-mente-v2`. Si aparece `memory_recovery_pending`, enviar `cancelar` como prep de ambiente (no cuenta). Entonces turno 1.
5. 25 repeticiones: 5 de cada familia congelada en `tests/data/goal10_corpus_freeze.v1.json` → `conversation`, `media.play`, `audio.volume`, `system.status`, `system.settings`. Acciones reversibles en físico; Spotify está instalado; brillo WMI 100; volumen scalar 1.0 muted true.
6. Cada turno: entrada, salida visible, operación/plan, hechos contemporáneos, postcondición, terminal, veredicto. Privado en `artifacts/goal10/private/turns-10.3.jsonl` (gitignored). Resumen versionable sin texto de usuario.
7. El lote `private/failed-batches/10.3-batch0-launch1-memory-recovery-hijack.jsonl` y las 2 líneas actuales de `turns-10.3.jsonl` **no** son de los 50. El bloque arranca en 0.
8. Afirmación falsa, efecto no pedido o prosa fija → corregir causa mínima, test dueño dos veces, **reiniciar este bloque desde 0**.
9. Petición in-scope imposible por ambiente → `FALLO_DE_AMBIENTE` en `artifacts/goal10/environment/10.3.md`, pausa, no skip, no 10.4.
10. Cierre 10.3 sólo con 50/50 pass individuales, cero invariantes duros rotos, artefacto privado + resumen, handoff, commit y push. Entonces, y sólo entonces, `10.4_USO_REAL_B.md`.
