# Sexto corte productivo: control global de audio

Estado del corte: implementado y verificado en `33b62bc`. Añade control absoluto
del volumen y del silencio de la salida predeterminada de Windows, con intención
durable, postlectura independiente, replay conservador y recuperación desde la
GUI. La auditoría final quedó en cero P0/P1 después de corregir el arnés físico.

Este corte no cierra ningún Must adicional ni los bloqueantes B-004/B-005/B-006.
No añade control por aplicación, micrófono, reproducción multimedia, voz,
composición libre, conversación general, instalador ni aceptación en Windows
limpio.

## Alcance exacto

El catálogo productivo del core contiene diez operaciones. Nueve son capacidades
interactivas exigidas por el handshake de la GUI; `app.status` continúa como
salud interna. Las dos operaciones nuevas son:

| Operación | Argumento exacto | Riesgo | Efecto |
|---|---|---|---|
| `audio.volume` | `level`, entero 0–100 | `low_reversible` | fija el volumen maestro absoluto |
| `audio.mute` | `state`, booleano | `low_reversible` | silencia o reactiva explícitamente |

El target es uno solo: el endpoint de salida predeterminado de Windows para
`eRender/eMultimedia`. No se infiere otro dispositivo ni se recorre el conjunto
de endpoints. El volumen es absoluto; no existen en esta slice `sube un poco`,
volumen relativo, media keys ni consultas de estado.

## Oráculo histórico congelado

La auditoría del corpus encontró 529 filas únicas relacionadas con audio y 397
filas de producto clase `user_mission`. Las dos misiones standalone de volumen
y mute reúnen 335 mensajes: 248 de volumen y 87 de mute. Este corte congela
solo el subconjunto inequívoco que puede ejecutarse sin planner ni contexto
adicional.

| Familia | IDs de producto | Literales normalizados |
|---|---:|---:|
| volumen absoluto | 127 | 97 |
| mute/unmute explícito | 16 | 12 |
| **Unión** | **143** | **109** |

La unión proviene de 14 rutas `source` y dos misiones. Los digests SHA-256 son:

- volumen: `b1ddcd0623b9456f6852a7dc1b6c00ff1b4529ad24f2a0bcb1b0fce3c99d2c0b`;
- mute: `0059de3914395a5e07beb2b3ccc57691bac2735d44455c7e0438a28dcf5f97c1`;
- unión: `f2a35f4bba3bfdb7a3eadc4d3139f66308fe7397fa3e92305c594bfbe9c9fe48`;
- negativos duros: `85dc84b9a95b2a39417f9d5fd57520cf5639b151e4572331fad3a79bc65d3b30`.

Los 143/143 enrutan al nombre y argumento exactos. Además, 156 negativos
congelados y el barrido de las 14.836 filas mantienen fuera de la slice
relativos, sesiones por aplicación, micrófono, consultas, condiciones,
negaciones y composiciones; una regresión separada cubre UTF-16 malformado.

Quedan 192 mensajes de las dos misiones standalone fuera de este corte, además
de composiciones y otras familias de audio. Por eso 143/143 no significa cubrir
las 529 filas globales ni cerrar la familia histórica completa.

## Parser natural y frontera de composición

La GUI acepta gramáticas completas y finitas ES/EN/spanglish, por ejemplo:

- `pon el volumen a 30`, `volume to 30`, `set the pc volume to 30 percent`;
- `mute`, `silencia el audio`, `mute system porfa`;
- `unmute`, `desmutea el pc`, `unmute the sound please`;
- la corrección auditada exacta `no, mejor pon el volumen a N`.

El parser de volumen pliega mayúsculas y diacríticos y colapsa únicamente
espacios horizontales. Mute usa una normalización separada que preserva
diacríticos para no confundir conversación histórica con una orden. Así,
`silenciá el audio` no se promueve por accidente a la acción exacta
`silencia el audio`.

La frase debe coincidir completa. Se rechazan nivel fuera de 0–100, decimales,
relativos, múltiples números, aplicación/sesión, micrófono, media keys,
preguntas, condiciones, negaciones y combinaciones con otra operación. Esta
frontera evita presentar un parser finito como conversación o planner general.

## Provider Windows y evidencia durable

El provider usa la Endpoint Volume API de Windows mediante interfaces COM
generadas para NativeAOT. Abre el endpoint predeterminado con
`IMMDeviceEnumerator::GetDefaultAudioEndpoint`, activa
`IAudioEndpointVolume` y limita su superficie a:

- `Get/SetMasterVolumeLevelScalar` para el scalar maestro 0–1;
- `Get/SetMute` para el estado explícito de silencio;
- `IMMDevice::GetId`, que nunca sale en crudo: solo se persiste SHA-256.

Cada invocación se serializa bajo un mutex de producto y sigue este orden:

1. observa endpoint, scalar y mute iniciales;
2. persiste una intención durable ligada a invocation ID, operación, argumento,
   hash del endpoint y baseline exacto;
3. hace una prelectura independiente y falla cerrado si cambió endpoint u otra
   dimensión;
4. emite como máximo un setter;
5. reabre el endpoint y corrobora el postestado;
6. persiste un receipt terminal antes de devolver éxito.

La tolerancia de volumen es de dos puntos porcentuales para admitir
cuantización del hardware. Mute exige coincidencia booleana y conserva el
scalar con tolerancia `0,0001`. Cambiar volumen no autoriza cambiar mute, y
cambiar mute no autoriza cambiar volumen.

Si existe una intención sin receipt, el replay nunca repite el setter. Solo
observa el estado actual y puede concluir:

- objetivo ya presente y otra dimensión preservada: `reconciled=true`,
  `applied=false`;
- endpoint cambiado o evidencia contradictoria: fallo terminal honesto;
- plataforma temporalmente inaccesible: estado pendiente reintentable con la
  misma identidad.

`reconciled` es evidencia observacional, no causal. Incluso si un setter devuelve
HRESULT fallido y la postlectura coincide con el objetivo, el receipt queda
`applied=false` y el mensaje dice que BAXY confirmó el estado; nunca afirma que
lo produjo. No se promete exactly-once.

El store de audio falla cerrado al llegar a 16.384 registros o 64 MiB. No poda
intenciones sin un diseño de confirmaciones/tombstones: rechaza nuevos efectos
antes de perder la evidencia necesaria. Es una deuda P2 de operabilidad, no una
autorización para evicción insegura.

## Recuperación en core y GUI

El protocolo incorpora `pending` como estado no terminal. Un resultado
reintentable no se registra como completion en el journal. La GUI conserva el
mismo `missionId`, `invocationId`, operación y argumentos, bloquea otras rutas y
solo permite continuar mediante `continuar`/`continue`/`retry` o la misma orden
exacta.

Al reiniciar, el outbox reconstruye esa ruta sin volver a interpretar lenguaje
natural. Una respuesta reconciliada usa lenguaje no causal, por ejemplo
`Confirmé que el volumen del sistema está en… tras recuperar el intento`.
No hay rollback ni reaplicación automática cuando el efecto es incierto.

## Gate físico NativeAOT

El gate explícito ejecutó un `baxy-core.exe` NativeAOT real sobre el endpoint
predeterminado de esta máquina. Antes de acceder a Core Audio, un preflight
separado demostró que el ciclo del proceso podía terminar. El arnés asignó el
core a un Job Object `KILL_ON_JOB_CLOSE`, limitado a un proceso, y condicionó
restauración y borrado de estado a salida corroborada.

| Paso | Evidencia observada |
|---|---|
| AOT temporal | 5.199.360 bytes; SHA-256 `7a45f1e8e49d169db401eca87bf95896e6a883db26f7cf2f8e977d570dd5a225` |
| Endpoint | hash `7b631a2d2e08e0bbbb444624678a6fc32c73de439620737867515513f3e31218`; ID crudo no emitido |
| Baseline | scalar `0,98`; 98 %; mute `false` |
| Volumen | request 88; scalar físico `0,88`; mute preservado `false` |
| Mute | request `true`; scalar preservado `0,88` |
| Replay | ambas invocaciones `replayed=true`; sin otro efecto observado |
| Restore | mismo hash; scalar `0,98`; 98 %; mute `false` |
| Cleanup | cero `baxy-core`; cero directorios físicos temporales; Notepad 5472 preservado |

El primer intento detectó la terminación como no corroborada por una carrera de
espera con timeout cero y, correctamente, omitió la restauración automática. El
baseline capturado se restauró de inmediato y se verificó antes de repetir. El
arnés se corrigió con espera acotada real y preflight; el segundo intento pasó
completo. La historia —dos intentos, uno fallido y uno aprobado— permanece en
`artifacts/product/audio_control_gate.json`.

Este incidente es evidencia del comportamiento fail-closed del arnés, no una
prueba de sonido audible. El AOT temporal fue eliminado después del gate y no es
el distribuible ni un instalador.

Después del gate se reconstruyó el directorio distribuible local sobre
`33b62bc`: 14 archivos y 54.831.324 bytes. Sus hashes SHA-256 son
`4c0378c01ffd67d6949f90f1c0f2f611300cea2450e32ef1ac5756d36fb3553a`
para el manifiesto,
`f017ba4babdf307f6dc5a3403089e9d14e59ed76c6c62526693bea907b80be80`
para `Baxy.exe` y
`0f794ae353a22e2b6bdbc21da51513e4116c776d12e170c02616ce440d38cc94`
para `baxy-core.exe`. Las 14/14 entradas se verificaron contra bytes y hashes.
El core publicado anunció diez capacidades, cerró con código 0 y stderr vacío.

Una captura funcional de la app publicada completó shell→core→nota con
`core_ready`, una misión terminada, outbox vacío y cero procesos residuales. La
imagen 980×680 pesa 71.521 bytes y tiene SHA-256
`4eb2dd03bc0d1ba32c452d2b92c0d13124acb12e7651b4e59133abdb702ca6b6`.
Esta captura valida el handshake ampliado; no ejecuta audio desde la GUI.

## Evidencia ejecutada

| Evidencia | Resultado |
|---|---:|
| Contratos .NET | 25/25 |
| Kernel .NET | 29/29 |
| Provider Windows .NET | 118/118 |
| Integración .NET | 493/493 |
| **Total .NET Release no físico** | **665/665** |
| Python canónico | 59/59 + 148 subtests |
| Total principal no físico | 724/724 |
| Oráculo histórico curado | 143/143 |
| Gate físico explícito | 1/1 en el rerun aprobado |
| Manifiesto del build local | 14/14 archivos |
| Captura app publicada | core listo, misión terminada, outbox 0 |
| Auditoría final | 0 P0/P1 |

Las regresiones cubren cuantización, preservación de la otra dimensión,
cambios de endpoint, setter con HRESULT fallido, corrupción y capacidad del
store, crash antes/después del efecto, replay sin segundo setter, exclusión
mutua, receipts contradictorios, estado `pending`, reinicio de la GUI y mensajes
no causales. El publish NativeAOT no emitió warnings.

Los artefactos protegidos permanecieron byte a byte intactos:

- `artifacts/corpus_cutoff/source_manifest.json`:
  `9da873e4b30dd81d1cc85d6e9bf4b19fb13aa96e8fcc5ce3b1f8265012ca59b0`;
- `scripts/freeze_historical_sources.py`:
  `27acb6ccc34b6820ab8614a19d41409645aabeb151803bfec4d34843e6c4ae5c`;
- `artifacts/technology_tournament/protocol.json`:
  `383a9e54cfc5a186de61f060aeb2a6cd013bab3ec21bdeb387063d935d99a892`.

## Límites y deuda explícita

- La evidencia física cubre el estado de control de un endpoint
  `eRender/eMultimedia` en una máquina; no demuestra sonido audible, otros
  dispositivos, sesiones, drivers, modo exclusivo ni hardware diverso.
- No hay volumen relativo, por aplicación, micrófono, consultas, media keys ni
  composición con otras operaciones.
- El oráculo cubre 143 IDs; quedan 192 mensajes de esas dos misiones standalone.
  Además quedan composiciones y el resto de las 529 filas globales por
  clasificar.
- Una reconciliación confirma un estado observado; no prueba causalidad ni
  exactly-once y no activa rollback/reapply automático.
- El límite 16.384/64 MiB es fail-safe, pero requiere una política futura de
  confirmaciones o tombstones para operación prolongada.
- El build local ya fue reconstruido después del sexto corte, pero continúa
  siendo un directorio de desarrollo: no es MSI/MSIX, no está firmado y no
  acredita instalación, actualización, rollback o desinstalación en Windows
  limpio.
- No hay nueva evidencia de Narrator/NVDA, DPI al 200 %, GPU de 4 GB, voz real o
  VM limpia.
- El progreso permanece en 5/15 Must (33,3 %). Este corte reduce B-004, pero
  B-004/B-005/B-006 siguen abiertos.

## Adenda 2026-07-15: corte finito audio global 28

La revisión `2026-07-15-audio-status-v3` amplía esta slice sin planner ni
clasificador general. Promueve exactamente 28 IDs antes congelados como
negativos: 12 alias nominales de volumen absoluto y 16 consultas de estado. El
oráculo conjunto pasa a 171 IDs/120 literales/14 fuentes/tres misiones; conserva
128 negativos duros.

`audio.status` es una única operación pública, sin argumentos y de riesgo
`read_only`. Lee volumen y mute de la salida predeterminada bajo el mismo lock
global, devuelve solo el hash SHA-256 del endpoint y el estado corroborado, y no
ejecuta setter ni escribe intención/receipt durable. Sus 16 IDs tienen digest
`cd3512c246ca7b4fe29f98e944eac5885cd73ca478a4fa9183d21edb409c60fb`.

Los JSONL canónicos se regeneraron exclusivamente con el builder y una
enmienda reproducible; preview y salida canónica coincidieron 4/4 byte a byte.
La adenda añade pruebas deterministas ES/EN/spanglish y deja el catálogo runtime
en 22 operaciones totales/21 interactivas. No agrega evidencia física nueva: el
gate original sigue acreditando únicamente volumen/mute en un host.

## Referencias técnicas

- Microsoft Learn, Endpoint Volume Controls:
  <https://learn.microsoft.com/en-us/windows/win32/coreaudio/endpoint-volume-controls>.
- Microsoft Learn, `IAudioEndpointVolume::SetMasterVolumeLevelScalar`:
  <https://learn.microsoft.com/en-us/windows/win32/api/endpointvolume/nf-endpointvolume-iaudioendpointvolume-setmastervolumelevelscalar>.
- Microsoft Learn, `IMMDeviceEnumerator::GetDefaultAudioEndpoint`:
  <https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-immdeviceenumerator-getdefaultaudioendpoint>.
- Microsoft Learn, `IMMDevice::GetId`:
  <https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-immdevice-getid>.
- Microsoft Learn, COM source generation:
  <https://learn.microsoft.com/en-us/dotnet/standard/native-interop/comwrappers-source-generation>.
