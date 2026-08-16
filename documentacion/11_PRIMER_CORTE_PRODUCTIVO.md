# Primer corte productivo de BAXY

Estado: implementado como corte vertical acotado; pendiente de expansión
funcional y aceptación de producto. Este documento no cierra ningún Must ni el
bloqueante B-004.

Nota histórica: `documentacion/13_TERCER_CORTE_NOTAS_NATURALES.md` amplía
después la GUI a `read/trash/restore`. Las limitaciones siguientes describen el
checkpoint del primer corte, no el runtime vigente.

## Qué existe

La solución `Baxy.slnx` materializa la arquitectura ganadora como dos procesos:

usuario → shell .NET 10 WPF → JSONL local `baxy.local.v1` → core .NET 10
NativeAOT → operación tipada → efecto local → journal/replay → respuesta.

El catálogo del core contiene exactamente:

- `app.status`;
- `note.create`;
- `note.read`;
- `note.list`;
- `note.trash`;
- `note.restore`.

Los seis contratos pueden invocarse en la frontera del core. La GUI no ofrece
todavía esa amplitud: su parser natural reconoce frases acotadas para crear y
listar notas. `note.read`, `note.trash` y `note.restore` no tienen enrutamiento
natural desde el compositor. No existe conversación general en este corte.

`note.list` es una consulta paginada: `limit` vale 50 por defecto, acepta como
máximo 100 y se combina con `offset`. El provider devuelve resúmenes que
excluyen el contenido y entregan solo los datos necesarios para la lista. El
store admite un corpus máximo de 512 notas.

## Separación de responsabilidades

| Proyecto | Responsabilidad del corte |
|---|---|
| `Baxy.Contracts` | Contratos, validación y JSON compatible con NativeAOT |
| `Baxy.Kernel` | Registro, ejecución, huellas, journal y replay |
| `Baxy.Providers.Windows` | Store local de notas |
| `Baxy.Core` | Proceso NativeAOT y servidor JSONL por stdin/stdout |
| `Baxy.App` | Shell WPF, ciclo de vida del core y presentación |

## Persistencia local

El store guarda cada nota en un documento JSON UTF-8. El documento lleva un
SHA-256 de integridad. Cada mutación se prepara en un temporal del mismo
directorio, se reemplaza de forma atómica y conserva la versión anterior como
backup recuperable. La lectura valida el documento y puede recuperar la copia
válida.

Este mecanismo no cifra el contenido. Su SHA-256 no usa una clave y por tanto
no es una MAC.

## Journal y replay

El journal JSONL registra el inicio y término de cada invocación. Cada registro
incluye el hash del anterior, formando una cadena SHA-256 que se valida al
abrir. El runtime conserva el resultado terminado por identificador de
invocación y huella de petición:

- repetir identificador y petición devuelve el resultado guardado sin repetir
  el efecto;
- reutilizar el identificador con una petición distinta se rechaza.

Una invocación que quedó únicamente en fase `started` no se reaprovecha: una
petición en conflicto devuelve `idempotency_conflict`, y el core continúa
atendiendo solicitudes posteriores.

El journal tiene un tope duro de 64 MiB. Su compactación atómica conserva de
forma exacta todos los identificadores, huellas y respuestas terminadas, sin
caducarlos. Cada mutación admitida reserva 2 MiB para poder registrar su
término; las reservas de invocaciones `started` incompletas se reconstruyen al
reiniciar. Si no existe capacidad, el core rechaza antes de ejecutar el efecto
y el shell conserva la misma identidad durable para reintentar.

Un fallo inesperado de almacenamiento o integridad durante una mutación no se
convierte en una respuesta terminal falsa: deja la invocación incompleta y
reintentable con el mismo ID.

La cadena no usa HMAC. Es evidencia de consistencia local, no una firma de
autenticidad.

## Frontera y ciclo de vida de la GUI

La frontera JSONL está acotada a 1 MiB en ambas direcciones: el core limita su
entrada y la GUI limita la salida antes de asignarla. La captura de stderr
también está acotada. La GUI mantiene el mismo `missionId` y `invocationId`
durante sus reintentos hasta recibir una respuesta terminal, de modo que el
journal pueda resolver el replay sin duplicar efectos.
Antes de enviar, persiste la petición en un outbox durable. Ese outbox sobrevive
al reinicio completo del shell y elimina la entrada solo después de recibir una
respuesta terminal. Cada entrada lleva un checksum SHA-256 canónico para
detectar corrupción accidental. Es un archivo JSON en texto plano, sin cifrado
ni HMAC, limitado a 1 MiB y 128 entradas; ante corrupción o rutas reparse falla
cerrado.

Los fallos normales al iniciar el core o completar su saludo se presentan como
`No disponible`; la GUI permanece abierta en ese estado degradado. Ante timeout
se señala la desconexión antes de propagar el error, se evita una disponibilidad
`ready` falsa y se rechazan envíos posteriores. El hijo se registra desde que
arranca y la limpieza intenta cerrarlo incluso si falla su asociación al Job de
Windows. Los scripts validan cada ancestro, ADS y puntos reparse, y ligan la
limpieza a handles de los procesos que ellos mismos crean. Una prueba hostil de
junction preservó un centinela externo al destino autorizado.

## Evidencia disponible

| Evidencia | Resultado y alcance |
|---|---|
| Suite .NET Release | 101/101: Contracts 23, Kernel 26, Provider 16, integración 36 |
| Suite histórica Python | 41/41; corrida conjunta total: 142 pruebas |
| Captura | `artifacts/product/product_notes_slice.png`, 980×680; `core_ready`, `mission_completed`, una nota, cero procesos residuales y outbox vacío tras el terminal |
| Build local | 14 archivos de carga, 48.396.888 bytes, más el manifiesto |
| Manifest | SHA-256 individual de los 14 archivos |

El build reúne shell y core para ejecución local. No es un MSI/MSIX, no es un
instalador y no demuestra instalación, actualización o desinstalación en una
máquina Windows limpia.

## Fuera del alcance demostrado

Este corte no declara voz, visión, memoria de usuario, control de hardware ni
conversación general. Tampoco demuestra el ledger histórico completo, gates
físicos, ausencia final de P0/P1 o distribución instalable. Esos requisitos
permanecen pendientes en la matriz de aceptación.

El outbox durable mejora la recuperación local y su checksum detecta corrupción
accidental, pero al estar en texto plano y sin HMAC no demuestra
confidencialidad ni autenticidad frente a un atacante.
El progreso permanece en 5/15 Must y B-004 sigue abierto.

## Próximo criterio de avance

La frontera actual debe conservar sus contratos, replay, recuperación, GUI y
evidencia de build mientras se cierran los gates restantes. Solo después
corresponde ampliar el catálogo y la entrada natural, siempre ligados a
misiones y regresiones del ledger histórico.
