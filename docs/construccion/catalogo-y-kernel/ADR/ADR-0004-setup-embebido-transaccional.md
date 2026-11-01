# ADR-0004 — Setup embebido y motor transaccional por usuario

- Estado: Aceptado para foundation de entrega.
- Fecha: 2026-07-15.
- Ámbito: `Baxy.Setup.exe`, validación del paquete embebido y publicación de
  versiones en `%LOCALAPPDATA%\Programs\BAXY`.
- Fuera de alcance: UX final, integración Windows, desinstalación, firma,
  compatibilidad de datos, VM limpia y lifecycle 1.0 completo.

## Contexto

El ZIP reproducible resolvió bytes y procedencia, pero una extracción manual no
puede ofrecer actualización, punteros estables, recuperación ni una frontera
segura ante payload corrupto. La entrega necesita un único ejecutable que no
dependa de PowerShell, .NET instalado ni el árbol de desarrollo.

## Alternativas

1. **Distribuir solo ZIP y sidecar.** Rechazada: delega al usuario el destino,
   extracción y reemplazo de una versión activa; no ofrece recovery.
2. **Introducir de inmediato WiX/MSI, MSIX, NSIS o Inno Setup.** Diferida: esas
   tecnologías resuelven integración Windows, pero no reemplazan el contrato de
   payload, journal y compatibilidad de datos que todavía debe cerrarse.
3. **Bootstrap .NET NativeAOT con ZIP atestado embebido y motor propio.**
   Aceptada como foundation mínima, autocontenida y auditable.

## Decisión

- Release de Setup se construye únicamente desde HEAD limpio y worktree
  detached. El ZIP y su atestación son recursos obligatorios.
- El ejecutable es `WinExe` AMD64/PE32+ NativeAOT, usa `/Brepro`, excluye
  símbolos de entrega y declara honestamente `NotSigned`.
- El paquete se vuelve a parsear de forma independiente: layout Stored exacto,
  CRC real, SHA-256, manifiesto v3 canónico, checksums, commit, epoch,
  `content_id` y límites.
- El destino operativo es canónico y no configurable. Cada versión es
  inmutable; `current` y `current.previous` solo contienen SemVer válidos.
- Toda transición se journaliza. Recovery es consciente de la operación y de
  las identidades previas; estados ambiguos, reparse, ADS o hardlinks fallan
  cerrados.
- El builder no reemplaza outputs: `OutputRoot` debe ser nuevo. La promoción es
  un rename de directorio dentro de la raíz autorizada y se verifica dos veces.
- El programa de entrega no expone rollback hasta resolver compatibilidad de
  datos y probar lifecycle completo.

## Evidencia

Dos cadenas completas del commit `5dad02a` produjeron producto, ZIP y Setup
idénticos. `Baxy.Setup.exe` mide 85.858.304 bytes, SHA-256
`50b8b8d415a822efabfa8986f3ec10d8d20d940dd2feca84b97f547b65452c7a`.
Los dos publishes y ambos outputs promovidos ejecutaron verificación embebida
con exit 0. El motor aprobó 61 tests; el builder, 15; las auditorías no dejaron
P0/P1. Evidencia: `artifacts/setup/setup_package_gate.json`.

## Consecuencias

- El mismo contrato puede ser consumido después por un integrador MSI/MSIX o
  registro de desinstalación sin cambiar el formato del payload.
- SHA-256 y reproducibilidad no sustituyen firma del editor.
- El artefacto ya puede verificarse offline, pero no se denomina instalador 1.0
  terminado ni aprueba Must 14.
- B-005 cambia de “Setup inexistente” a “instalación limpia e integración/
  lifecycle incompletos”.

## Criterio de reapertura

Reabrir si el contrato de datos exige rollback incompatible, una prueba limpia
encuentra estado no recuperable, aparece un P0/P1, se adopta un formato de
paquete distinto o firma/MSI/MSIX requieren cambiar las identidades persistidas.
