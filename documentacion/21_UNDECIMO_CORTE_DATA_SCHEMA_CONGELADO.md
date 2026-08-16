# Undécimo corte: `data_schema=1` congelado

Fecha del corte: 2026-07-15

Commit de código atestiguado: `3f547efb7eca0289548071efee0637fcdd9ba7c4`

Estado: aprobado como contrato de compatibilidad y reproducción same-host; no
aprueba todavía el lifecycle completo de Windows.

## Resultado

BAXY congela su primer esquema de datos de usuario como el entero exacto
`data_schema=1`. Paquete, Setup, atestación instalada, punteros de activación y
recuperación transaccional transportan o validan esa identidad. Un install,
update o rollback con otro esquema falla antes de cambiar la activación.

No existe una migración implícita. Una versión futura que necesite cambiar el
formato de `%LOCALAPPDATA%\BAXY` deberá traer una migración explícita,
transaccional, reversible y probada; cambiar el número no autoriza a interpretar
ni reescribir datos existentes.

## Contratos versionados

| Superficie | Esquema |
|---|---|
| Manifiesto de producto | `baxy-product-build-v4` |
| Manifiesto de Setup | `baxy-setup-build-v2` |
| Puntero `current` | `baxy-current-v2` |
| Atestación de versión instalada | `baxy-installed-version-v2` |
| Transacción de install/update/rollback | `baxy-install-transaction-v2` |
| Atestación del payload embebido | `baxy-setup-embedded-package-v2` |
| Evidencia del verificador embebido | `baxy-setup-embedded-verification-v2` |

Los JSON canónicos exigen además posición, conjunto y tipo exactos. Por
ejemplo, `true`, `"1"`, `0` y `2` no son equivalentes a `1`.

## Reproducción física

Se construyeron dos cadenas independientes desde el mismo HEAD limpio:

| Artefacto | Réplicas | Resultado | Bytes | SHA-256 |
|---|---:|---|---:|---|
| Producto | 2 | árboles idénticos | 82.842.651 | manifiesto `e282d188…f746` |
| ZIP | 2 | idénticos byte a byte | 82.845.989 | `15fc366b…b491` |
| `Baxy.Setup.exe` | 2 | idénticos byte a byte | 85.864.448 | `3059917e…383d` |

Los dos publishes ejecutaron el verificador embebido durante el build. Después,
los dos ejecutables promovidos se verificaron dos veces cada uno: cuatro
ejecuciones adicionales, todas con código de salida cero y evidencia idéntica
SHA-256 `dcce6166…0225` con `data_schema=1`.

La evidencia sanitizada y completa está en
`artifacts/setup/setup_data_schema_gate.json`. Las salidas físicas permanecen
fuera de Git bajo `artifacts/product/build/` y `artifacts/setup/build/`.

## Regresión del corte

- .NET Release: **1.277/1.277** pruebas superadas.
- Python: **112/112** pruebas superadas y 172 subtests.
- Builder de Setup: **16/16**.
- Formato y `diff-check`: limpios.

## Límite honesto

Este corte no tocó `%LOCALAPPDATA%\Programs\BAXY` ni los datos reales del
usuario. No afirma instalación limpia, primer arranque, acceso del menú Inicio,
Apps instaladas, update, rollback físico, uninstall keep/purge, recuperación de
un corte de energía, VM limpia ni autenticidad del editor. Esas superficies
siguen perteneciendo a B-005/B-006.

La consecuencia arquitectónica ya queda fijada: el host estable y el acceso
directo siempre resolverán la versión activa mediante el puntero verificado;
los datos permanecen fuera de la raíz de programa y uninstall conserva datos
por defecto.
