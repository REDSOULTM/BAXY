# Décimo corte — Setup embebido y reproducible

Este corte convierte el ZIP autocontenido del noveno corte en un único
`Baxy.Setup.exe` NativeAOT para Windows x64. El ejecutable lleva dentro el ZIP
exacto y una atestación canónica, los verifica antes de cualquier instalación y
solo admite como destino operativo `%LOCALAPPDATA%\Programs\BAXY`.

El resultado es una **base de entrega e instalación por usuario**, no el cierre
del instalador de BAXY 1.0. Todavía no se ejecutó una instalación en Windows
limpio, no hay integración de Inicio/Aplicaciones instaladas, interfaz visible,
primer inicio, desinstalador ni actualización y rollback de datos demostrados.
El progreso permanece en **5/15 Must (33,3 %)** y B-004/B-005/B-006 siguen
abiertos.

## Contrato implementado

- `src/Baxy.Setup` es `WinExe`, `win-x64`, autocontenido y NativeAOT. Release
  exige el ZIP y su atestación como recursos embebidos; un publish de entrega
  sin ambos falla.
- Sin argumentos, `Baxy.Setup.exe` verifica el paquete y llama al motor
  transaccional sobre la raíz canónica por usuario. No acepta una ruta elegida
  por CLI.
- `--verify-embedded --evidence <ruta-nueva-absoluta>` es el modo interno del
  gate. Comprueba ZIP, manifiesto, checksums, atestación, hashes y `content_id`
  sin instalar.
- El parser exige nueve entradas Stored, orden y timestamps canónicos, CRC32
  calculado sobre los bytes reales, SHA-256, manifiesto v3 exacto y límites de
  tamaño. Rechaza reparse points, ADS y hardlinks.
- El motor publica versiones inmutables, mantiene `current` y
  `current.previous`, escribe journal durable y recupera cada corte de fallo
  modelado. Una transición de instalación debe avanzar SemVer.
- El rollback existe en el motor y sus pruebas, pero el programa de entrega no
  lo expone: la compatibilidad de datos entre versiones todavía no está
  resuelta.
- `scripts/build_setup.ps1` exige HEAD limpio, recompone desde un worktree
  detached, aísla todos los outputs de .NET, usa `PathMap`, `/Brepro` y
  `SOURCE_DATE_EPOCH`, y solo promueve a un `OutputRoot` nuevo. Nunca reemplaza
  ni elimina una entrega previa.

## Reproducción física

La cadena completa se ejecutó dos veces, en serie y desde snapshots Git
independientes del commit `5dad02a669df778b6c441ca942720525e16278ee`:

| Artefacto | Réplicas | Resultado | Bytes | SHA-256 |
|---|---:|---|---:|---|
| árbol de producto, 7 payloads | 2 | árboles idénticos | 82.842.646 | manifiesto `13aa08fc…abcf` |
| ZIP Stored, 9 entradas | 2 | archivos idénticos | 82.845.968 | `9a7acc74…2532` |
| `Baxy.Setup.exe` | 2 | archivos idénticos | 85.858.304 | `50b8b8d4…2c7a` |
| `setup-manifest.json` | 2 | archivos idénticos | 1.068 | `dc6ab570…6ee7` |

Cada build ejecutó físicamente el Setup publicado en modo de verificación.
Después de la promoción, ambos ejecutables finales volvieron a ejecutarse y
produjeron evidencia byte a byte idéntica con estado `passed`. El inspector de
entrega confirmó AMD64, PE32+, subsistema Windows GUI, recurso embebido, registro
REPRO, ausencia de CLR, tabla Authenticode, símbolos COFF y CodeView/PDB. El
estado Authenticode es honestamente `NotSigned`.

La evidencia sanitizada completa está en
`artifacts/setup/setup_package_gate.json`. No contiene rutas privadas ni los
outputs temporales del build.

## Fallos encontrados por el gate físico

La primera ejecución no se aceptó: una coma literal en el valor doble de
`PathMap` fue interpretada por MSBuild como separador de propiedades y produjo
`MSB4177`. El commit `864170f` la reemplazó por el escape controlado `%2C`; un
probe real corroboró que MSBuild entrega al compilador los dos mappings.

La siguiente ejecución compiló NativeAOT y aprobó PE y verificación embebida,
pero la revalidación final rechazó el input porque la atestación se había
escrito junto al ZIP y sidecar. El commit `5dad02a` separó esa metadata como
hermana dentro del trabajo aislado. Ambos fallos ocurrieron antes de promoción,
no dejaron `Baxy.Setup.exe` aceptado y quedaron cubiertos por regresión.

## Regresión y auditoría

- Suite .NET: **1.270/1.270**; desglose 37 Contracts, 44 Kernel, 61 Setup, 232
  Providers y 896 Integration. Dos gates físicos `[Explicit]` no fueron
  seleccionados por la corrida estándar.
- Suite Python: **110/110**, sin omitidas. `test_build_setup.py` aporta 15 casos
  dinámicos o contractuales para suciedad Git, layout exacto, sidecar enorme,
  hardlinks, junctions, ZIP/CRC, commit/epoch, SemVer, outputs inmutables,
  attestation y argumentos deterministas.
- Las auditorías adversariales del motor y del builder cerraron con cero P0/P1.
- Cleanup final: un solo worktree Git registrado, cero raíces temporales y cero
  procesos BAXY/Setup propios. El Notepad preexistente PID 5472 fue preservado.

## Límites que siguen bloqueando B-005

1. No se ejecutó la ruta de instalación sobre la raíz canónica, ni en este host
   ni en una VM Windows limpia.
2. Faltan acceso de Inicio, identidad de aplicación instalada, desinstalador,
   conservar/purgar datos y primer inicio desde `current`.
3. Faltan actualización real entre dos Setup, rollback compatible con el
   esquema de datos y recuperación física ante kill/corte de energía.
4. Los binarios first-party siguen sin firma. SHA-256 acredita consistencia con
   metadata confiada, no identidad del editor ni reemplazo adversarial de toda
   la entrega.
5. La reproducción es same-host con SDK y caches compartidas; linker nativo y
   Windows SDK son estado del host, no toolchain hermética ni prueba cross-host.
6. Las carreras activas de otro proceso bajo la misma cuenta y el flush durable
   de directorios ante pérdida súbita de energía quedan fuera del claim actual.

El siguiente corte de distribución debe añadir primero una prueba instalada
aislada y reversible, y después integración Windows y lifecycle completo. Solo
entonces corresponde reevaluar Must 14 y B-005.
