# Séptimo corte productivo: memoria privada local

Estado del corte: implementado y verificado en `478a19a`. Añade un ciclo local
explícito de memoria —habilitar, guardar, corregir, consultar, listar, borrar,
limpiar sesión y exportar— con transporte privado, persistencia cifrada,
confirmaciones visibles, payloads privados autenticados y export replay
verificado contra el artefacto. La auditoría del diff y la frontera de memoria
quedó en cero P0/P1; no es una afirmación sobre todo BAXY 1.0.

> **Addendum vigente (2026-07-15).** Este documento conserva la fotografía
> histórica de `478a19a`. Después de ese corte, el journal global incorporó una
> cadena HMAC-SHA-256 con clave dedicada protegida por DPAPI y regresiones
> fail-closed para key loss, truncado, rollback, tamper y journal legado. Bajo el
> contrato Codex→Fable v3, Gate 10 fue aprobado en su techo determinista con
> 405/405 pruebas focalizadas y cero P0/P1; la personalización transversal queda
> para Fable. Evidencia actual: `artifacts/product/memory_privacy_gate.json`.

Este corte no cierra ningún Must adicional ni los bloqueantes
B-004/B-005/B-006. El progreso permanece en 5/15 Must (33,3 %): la memoria aún
no personaliza otras acciones, y siguen pendientes deudas generales de
privacidad, autenticidad, empaquetado y validación en Windows limpio.

## Alcance exacto

El core anuncia 21 capacidades. La GUI exige 20 capacidades interactivas en el
handshake; `app.status` continúa como salud interna. Once capacidades pertenecen
a memoria:

| Operación | Riesgo exacto | Comportamiento |
|---|---|---|
| `memory.correct` | `low_reversible` | corrige una memoria mediante revisión auditable |
| `memory.disable` | `low_reversible` | bloquea nuevas lecturas y escrituras |
| `memory.enable` | `privacy_sensitive` | habilita memoria solo tras confirmación |
| `memory.export` | `privacy_sensitive` | exporta una vista inspeccionable con contenido sensible/secreto redactado tras confirmación |
| `memory.forget` | `work_loss` | borra el alcance exacto confirmado |
| `memory.list` | `read_only` | lista memoria visible de forma paginada y acotada |
| `memory.recall` | `read_only` | recupera como máximo cinco coincidencias |
| `memory.save` | `low_reversible` | guarda un dato explícito normal o personal |
| `memory.sensitive.save` | `privacy_sensitive` | guarda un dato sensible o secreto solo tras confirmación |
| `memory.session.clear` | `low_reversible` | elimina solo memoria de la sesión actual |
| `memory.status` | `read_only` | informa habilitación, conteos y capacidad |

La memoria nace deshabilitada. `memory.enable`, `memory.sensitive.save` y
`memory.export` requieren confirmación por privacidad; `memory.forget` la
requiere por pérdida de datos. Durante esa frontera, la GUI acepta una gramática
finita de confirmación —por ejemplo `sí`, `confirmo`, `dale`, `yes` o
`go ahead`— y cancelación —por ejemplo `no`, `cancela`, `cancel`, `never mind`
o `don't`—; nunca ejecuta el handler antes de una confirmación válida. Para
recuperación,
`memory.enable`, `memory.export` y `memory.forget` pueden persistir su petición
privada en el outbox antes del desafío; `memory.sensitive.save` conserva el
secreto solo en memoria hasta confirmar. Una
solicitud sensible no puede viajar como `memory.save`, y la limpieza de sesión
no puede alcanzar datos persistentes.

## Oráculo histórico congelado

El oráculo `baxy.memory.explicit-local.v1` está ligado a
`tests/data/historical_messages.jsonl`, SHA-256
`d9789574b41ff44fb057f17db696fd07140b299eb362a6b2636d86459bb804be`.
Normaliza en orden NFC, colapso de whitespace Unicode, trim y casefold Unicode.

| Grupo | IDs | Literales | Misiones | Fuentes | SHA-256 IDs | SHA-256 registros |
|---|---:|---:|---:|---:|---|---|
| guardar | 59 | 32 | 5 | 11 | `dfaf98dccac4d804c48714254a0fe78eda8205ee6636c9037305190928319b21` | `1520d0c0af522b0727cfedaeeda5627882639557112726a92c36581a2a7412f7` |
| recordar | 19 | 15 | 4 | 7 | `f12874133e043b16afa529d476d7545864ef3f951edf00375600d2e49c4e1dcf` | `879ee64edd018c9281dbaab504d1d2515b1d1c007427aab2824d88cd8df31480` |
| olvidar | 22 | 13 | 6 | 5 | `0631b9f80c184c6d48f8fd46950693dcf90378c6c979758ef7a71477313abd52` | `a4611fed6ede725f9395ee49b978e6e42633bf9019b8f8d623f9b3917fd872f0` |
| unión positiva | 100 | 60 | — | — | `5e4a1d981a4f909aafb58670421a0f4b5db51cdaa9a6e8036544c44510e63ff5` | `996ad8b25af253bf5e06a19b17886826880a0ae7c9fcc3e097878bba71f9a182` |
| corregir | 5 | 2 | 2 | 2 | `c84d4cbcad1ced1dcb4a51d09b86c1275e688135e2df40fe82a54eab5c06d2a9` | `9fc7e785d89825edc26e2f3a3ddcbb99371e41c6b2daed2d4f8764a6ce235745` |
| negativos duros | 34 | 34 | 15 | 15 | `ccb317011dd5abad31f091be29efd7aa040101ea2ba66799b50686ef30ecf318` | `536c08d3d4d64fd964fccaa54f3bb958a9d6c1c4e4107c4f85db3ceb273615b0` |

Guardar, recordar y olvidar son conjuntos disjuntos. La corrección comparte de
forma intencional un caso con los negativos duros para demostrar que no debe
degradarse a recall. Los negativos cubren secretos, payload ausente o ambiguo,
borrado ambiguo, composición, ruido documental, homónimos de “memoria”,
autorización general, uso temporal e inferencias sin consentimiento.

El oráculo no contiene un literal congelado de exportación: `memory.export`
proviene del requisito de producto. Por tanto, este corte no atribuye al corpus
una cobertura histórica inexistente.

## Frontera privada y raíz canónica

Los argumentos privados que llegan al core y los resultados privados de éxito
viajan como envelopes JSON cifrados y autenticados, ligados a dominio,
operación, `missionId`, `invocationId` y sesión. Challenge, expiración y
reconciliación viajan fuera del envelope. El bearer token de confirmación es
autoridad sensible: la App lo mantiene en RAM, lo redacta y no lo persiste ni lo
muestra; los fallos genéricos sí son metadatos públicos sin contenido privado.
El outbox conserva IDs, operación y checksum en claro, con los argumentos dentro
del envelope; el journal conserva secuencia, tiempo, fase, IDs, operación,
fingerprint, estado y error en claro, y solo el resultado privado exitoso queda
como envelope. Ni el contenedor del outbox ni el journal tienen HMAC. Un cambio
de identidad, propósito, sesión o ciphertext privado falla cerrado.

La protección genera una clave aleatoria AES-256, la envuelve con DPAPI
`CurrentUser` y cifra cada payload con AES-256-GCM y propósito autenticado. Si
la clave falta pero el sentinel permanece, el arranque falla antes de crear otra;
si la clave cambia y el sentinel original permanece, el digest no coincide. Un
sentinel ausente se recrea desde una clave DPAPI válida. Si faltan ambos se puede
crear otra clave, pero el ciphertext anterior no abre. El sentinel no detecta un
reemplazo coordinado de clave y sentinel por un adversario con acceso
`CurrentUser`.

La raíz privada solo puede ser un hijo directo de
`%LOCALAPPDATA%\BAXY\<hijo>`; el valor predeterminado es
`%LOCALAPPDATA%\BAXY\1`. Una raíz compartida, UNC, externa, igual al padre o con
prefijo hermano se rechaza. La raíz y las carpetas gestionadas por
`WindowsPrivateStorage` para clave/store/export se crean con su política privada;
la raíz recibe DACL protegida para el usuario actual y `SYSTEM`. La raíz, la
clave, el store y la exportación usan aperturas que validan owner, identidad final, disco local,
ausencia de reparse points y, para archivos, un solo hardlink; los handles de
directorio evitan intercambio por rename/junction durante esas operaciones. El
outbox durable y el journal aún operan por path/FileStream y no heredan esas
garantías por handle, aunque residan bajo la raíz protegida.

## Store, retención y recuperación

El store persiste snapshots, intención de mutación, watermark y copia de
recuperación dentro de la raíz privada. Todo contenido de memoria queda cifrado;
la publicación es atómica y el arranque reconcilia una mutación interrumpida sin
repetirla a ciegas. La capacidad falla antes del efecto:

- 512 registros y 4.096 receipts de mutación;
- snapshot claro máximo de 4 MiB, con reserva de emergencia para operaciones de
  privacidad;
- selector de 256 bytes UTF-8, valor de 4.096 bytes, hasta 16 tags de 64 bytes;
- recall de hasta 5 resultados; listado total de hasta 512 y páginas de hasta
  100.

La retención persistente no expira. La retención temporal creada por el parser
dura 24 horas; el store rechaza cualquier TTL mayor a 30 días y conserva un
watermark temporal para que un retroceso del reloj no reviva datos vencidos. La
retención de sesión se ata al identificador de sesión: comenzar otra sesión
purga la anterior, y `memory.session.clear` preserva siempre los registros
persistentes.

## Exportación y replay

`memory.export` escribe JSON de hasta 4 MiB en `Documentos\BAXY`, con nombre
derivado por SHA-256 de la invocación. `includeSecretValues` es siempre `false`:
en registros sensibles/secretos, selector, label y value se vuelven
`[REDACTED]`, tags queda vacío y sourceMissionId queda nulo. Sus valores
originales nunca salen. El resultado privado contiene
ruta, conteo y SHA-256, pero la proyección pública nunca muestra la ruta ni el
hash exactos.

Antes de aceptar un replay, el core vuelve a abrir la ruta canónica segura,
valida archivo regular y tamaño, recalcula SHA-256 y comprueba schema/version,
invocación, `includeSecretValues=false`, `recordCount` y longitud del array. No
revalida el schema ni el valor de cada registro; la coincidencia SHA-256 liga el
archivo byte a byte al hash guardado en el recibo privado autenticado. Un
archivo borrado, alterado o movido no produce un éxito histórico: BAXY admite
que puede existir un archivo, pero no afirma que siga presente e íntegro y
solicita una exportación nueva.

La confirmación y el éxito advierten que `Documentos\BAXY` puede estar
redirigido o sincronizado por la configuración de Windows. La exportación es,
por diseño, menos privada que el store cifrado.

## Evidencia ejecutada

| Evidencia | Resultado |
|---|---:|
| Suite .NET Release | 1.035/1.035 |
| Python canónico | 65/65 + 157 subtests |
| Catálogo core | 21 capacidades; 20 interactivas; 11 de memoria |
| Auditoría del diff/frontera de memoria | 0 P0/P1 |

Según la ejecución registrada durante el corte, el publish temporal de
validación de `478a19a` produjo `baxy-core.exe` de 6.252.544 bytes, SHA-256
`D32423255E93C51FDDDAA79E3A92C39C7F0D59D21D81A5F3C760CCA93F3A7EF7`,
desde un digest canónico de 101 archivos fuente/props/global, SHA-256
`b6c1eccf6aca5cc58c29daa6e8dd01d21b301d996cee034a08a83c1d16c0a0e7`.
El smoke registrado corroboró el handshake de 21 capacidades, las 11
operaciones de memoria anunciadas, `memory.status`, challenge/confirm de
`memory.enable` y `memory.list` vacío. El output ignorado permanece en
`src/Baxy.Core/bin/.../native/baxy-core.exe`; no se retuvo ni versionó un
artefacto independiente del smoke bajo `artifacts/product`.

El cleanup terminó sin procesos `baxy-core`, helper ni raíz temporal del smoke.
El Notepad preexistente PID 5472 se preservó y no formó parte de la prueba.

## Límites y deuda explícita

- La memoria se guarda, consulta, corrige, borra y exporta, pero todavía no se
  utiliza para personalizar notas, apertura de apps, audio, estado u otras
  acciones. Por eso no cierra el Must de memoria integral.
- Las notas y el outbox de operaciones generales ajenas a memoria continúan en
  texto claro. La protección privada de este corte no debe extrapolarse al resto
  del producto.
- Queda un P2 teórico sobre semántica NTFS sensible a mayúsculas bajo una
  precondición especial o elevada. No quedaron P0/P1 conocidos en la frontera
  auditada.
- El watermark detecta rollback parcial/incoherente y evita que un retroceso de
  reloj reviva temporales. No es un contador antirrollback externo: un rollback
  coordinado de current/recovery/watermark autenticados puede conservar
  coherencia y aceptarse.
- El journal conserva encadenamiento SHA-256 y replay, pero no HMAC; detecta
  corrupción accidental, no acredita autenticidad frente a un adversario con
  escritura local.
- No existe MSI/MSIX, firma, actualización, rollback ni desinstalación
  verificados. Tampoco hay aceptación de instalación y uso en un Windows limpio.
- El avance permanece en 5/15 Must y B-004/B-005/B-006 siguen abiertos.
