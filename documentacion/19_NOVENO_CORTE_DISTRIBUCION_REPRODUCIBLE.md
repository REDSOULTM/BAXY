# Noveno corte — distribución reproducible

> Estado histórico del noveno corte. El décimo ya añadió `Baxy.Setup.exe`; su
> alcance y límites vigentes están en
> `20_DECIMO_CORTE_SETUP_REPRODUCIBLE.md`. Las afirmaciones de este documento
> describen el checkpoint anterior y no deben extrapolarse al HEAD actual.

Este corte convierte el directorio de desarrollo en un paquete offline de
producto reproducible para Windows x64. El resultado se construyó dos veces
desde snapshots Git aislados del mismo commit y se empaquetó otras dos veces:
los árboles y los ZIP resultaron idénticos byte a byte.

No es todavía el instalador por usuario, una instalación en Windows limpio ni
una release firmada. Por eso el progreso global permanece en 5/15 Must y B-005
sigue abierto.

## Contrato de build

`scripts/build_product.ps1` publica únicamente este payload revisado:

1. `Baxy.exe`, WPF self-contained single-file;
2. cinco bibliotecas nativas WPF adyacentes y firmadas por Microsoft;
3. `core/baxy-core.exe`, .NET 10 NativeAOT self-contained.

El manifiesto canónico `baxy-product-build-v3` exige siete rutas exactas,
`win-x64`, configuración y casing canónicos, SemVer 2.0 estricto, hashes,
tamaños, orden ordinal, deployment declarado y `authenticity=not_provided`.
Rechaza PDB/DBG, bytes extra, rutas ambiguas o reservadas, colisiones sin
distinguir mayúsculas, Unicode no NFC, ADS y reparse points.

Un Release limpio solo se compila desde un worktree detached de `HEAD`. El SDK
se resuelve desde el `global.json` del snapshot y todas las llamadas a `dotnet`
se ejecutan con ese snapshot como directorio actual. Un árbol sucio se rechaza
antes de mutar outputs salvo override de desarrollo explícito; ese override
queda marcado `dirty=true` y nunca se presenta como Release.

## Contrato de paquete

`scripts/package_product.ps1` produce un ZIP determinista con nueve entradas:
las siete del payload, `build-manifest.json` y `SHA256SUMS`. Todas usan método
Stored, orden ordinal y timestamp derivado del commit. El inspector exige el
layout local/central/EOCD exacto: versiones, flags, atributos, nombres,
descriptores, tamaños, CRC, ausencia de extras/comentarios y regiones
contiguas.

El manifiesto se empaqueta desde los bytes inmutables ya validados. ZIP y
sidecar se preparan juntos en staging, se promueve el directorio completo y se
vuelven a validar y hashear dos veces en el destino final.

## Incidente de reproducibilidad cerrado

La primera réplica limpia reveló que `baxy-core.exe` variaba pese a
`Deterministic`, `PathMap` y `SOURCE_DATE_EPOCH`. Solo cambiaban tres bytes: el
`TimeDateStamp` COFF y sus dos copias en directorios debug del PE. El código y
las secciones AOT eran idénticos; la causa era que `link.exe` no recibía
`/Brepro`.

El commit `aac3e05` añade ese argumento bajo `PublishAot=true`, igual que el
core .NET medido en el torneo. Dos publishes posteriores desde snapshots
aislados quedaron completamente idénticos. No se normalizó ni parchó el
binario después de enlazarlo.

## Evidencia limpia

| Elemento | Evidencia |
|---|---|
| Commit fuente | `aac3e0509b848188e2cf50c01f09584af842bd90` |
| Procedencia | `dirty=false`; `git_head_snapshot` |
| Réplicas de build | 2; árboles idénticos |
| Payload | 7 archivos; 82.842.635 bytes |
| Manifiesto | 1.478 bytes; SHA-256 `3e6486ee67ec9f0c263a6f83ccbe34eacd0c6ca4dc7a21d34d59ac35e852e259` |
| `Baxy.exe` | 67.079.643 bytes; SHA-256 `57031a0fc5f79229bf8499da2cfb075e8872d7b9877a771bf7202a05e3ea9309` |
| `baxy-core.exe` | 7.376.384 bytes; SHA-256 `d2b03ef8fb4dc8c2379bbf3acde962b6b8fd15f04e59dd59729a22b52c204de5` |
| Réplicas de paquete | 2; ZIP idénticos |
| ZIP | 9 entradas Stored; 82.845.957 bytes |
| SHA-256 del ZIP | `11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9` |
| Pruebas Python | 95/95 |
| Pruebas .NET | 1.209/1.209 |
| Red-team packaging | 0 P0/P1 abiertos |

La evidencia sanitizada y machine-readable está en
`artifacts/product/product_package_gate.json`.

## Gates sobre el build limpio

- El core NativeAOT anunció 21 operaciones y aprobó identidad/uso GPU con tres
  adaptadores, dos medidos, uno no disponible, un fallo `unsupported`
  indexado, cero fallos globales, stderr vacío y exit 0.
- La GUI arrancó con `DOTNET_ROOT` apuntando deliberadamente a una ruta
  inexistente y `DOTNET_MULTILEVEL_LOOKUP=0`.
- El smoke 980×680 completó una nota natural y dejó cero procesos propios y
  cero datos de prueba. La captura mide 71.335 bytes y SHA-256
  `b9826c98cef137a21e2de42a1d010ef576c5dd30a668624916945101e13ad94d`.
- El Notepad preexistente PID 5472 se preservó.
- No aparecieron rutas privadas del repositorio o del usuario en búsqueda
  ASCII/UTF-16 de los ejecutables.
- `Baxy.exe` y `baxy-core.exe` no están firmados; las cinco bibliotecas nativas
  Microsoft tienen firma válida. El manifiesto no afirma autenticidad.

## Límites honestos

- La reproducibilidad es same-host, con SDK y caches compartidos; no es
  cross-host ni clean-room.
- El ZIP es un paquete offline, no crea accesos de Inicio ni registro de
  desinstalación y no prueba update, rollback o uninstall productivos.
- No hubo VM Windows limpia ni usuario estándar aislado.
- SHA-256 acredita consistencia contra metadata confiada, no identidad del
  editor ni resistencia al reemplazo completo del paquete.
- Un kill o corte eléctrico puede dejar staging GUID o metadata de worktree
  sin promover; el instalador deberá tener journal y recuperación.
- Los scripts no reclaman resistencia ante otro proceso hostil ejecutándose
  simultáneamente como la misma cuenta de Windows.

## Estado del producto

Este corte cierra la incertidumbre técnica same-host de build y ZIP
reproducibles para el SDK y caches observados, pero no aprueba por sí solo el
Must 14. En este checkpoint, el siguiente paso era `Baxy.Setup.exe` por
usuario, con versiones inmutables, `current/current.previous`, integración de
Windows, instalación limpia, update, rollback y desinstalación probados.
