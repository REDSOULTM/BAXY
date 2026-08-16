# Mensaje → misión → operación → prueba

Estado: **trazabilidad de especificación cerrada; implementación parcial**.

| Nivel | Artefacto | Cobertura |
|---|---|---:|
| Ocurrencia fuente | `artifacts/corpus_cutoff/source_manifest.json` | 122.744 |
| Mensaje consolidado | `tests/data/historical_messages.jsonl` | 14.836 |
| Mensaje de producto ES/EN/spanglish | `acceptance_scope=product_1_0` | 12.036 |
| Traza histórica ajena | `acceptance_scope=trace_only_not_acceptance_commitment` | 2.800 |
| Misión canónica | `tests/data/historical_missions.jsonl` | 2.084 |
| Mapeo mensaje→resultado | `tests/data/historical_message_mapping.jsonl` | 14.836 |
| Familia de operación | `OP_SPECS` del generador | 43 |

Los derivados usan schema 2 y revisión
`2026-07-15-audio-status-v3`. El alcance funcional obligatorio es
ES/EN/spanglish; las lenguas inequívocamente ajenas permanecen como
`trace_only_not_acceptance_commitment`. El detector `language` es heurístico y
no decide ese alcance por sí solo.

Cada mensaje tiene exactamente un resultado permitido: misión a implementar,
conversación/no-tool, requisito, restricción de ingeniería, negativa segura o
flujo de riesgo/dependencia. Cada misión conserva estado esperado, plan,
operaciones, roles de provider, verificación, respuesta natural, fallback,
riesgo y `acceptance_test_id`.

Garantías ejecutadas:

- IDs de mensaje y mapeo son únicos y sus conjuntos coinciden;
- toda misión referenciada existe;
- ninguna misión real de producto ES/EN/spanglish carece de operación; las
  trazas ajenas usan operaciones/providers vacíos y riesgo `no_effect`;
- cero misiones dinámicas sin clasificar;
- requisitos/fallos distintos no se fusionan;
- cada contrato canónico tiene todos los campos de acceptance;
- fuentes ignoradas por Git permanecen ligadas al cutoff;
- mensajes, misiones y mappings conservan `denied_operations`: 79 restricciones
  de no-acción y 98 mensajes con al menos un efecto denegado;
- los oráculos target enlazan exactamente 46 lanzamientos y 74 operaciones de
  instalación, sin crecimiento silencioso; gestión y compra quedan separadas.

Esto aprueba los Must 2 y 3 de especificación. No prueba que los providers de
BAXY 1.0 ya existan para todo el ledger o pasen todos sus gates.

## Trazabilidad ejecutada del sexto corte y su enmienda v3

El oráculo de audio global enlaza 171 IDs de mensaje, 120 literales, 14 rutas
`source` y tres misiones con `audio.volume`, `audio.mute` o `audio.status`.
Incluye exactamente 12 IDs de alias nominales para volumen y 16 consultas
read-only. Cada ID se resuelve
desde el corpus congelado y debe producir la operación y los argumentos exactos;
la suite conserva además negativos duros para conversación no auditada, control
por aplicación, micrófono, cambios relativos, negaciones y composiciones.

La cifra es una slice, no cobertura total. El corpus contiene 529 filas de audio
y 397 filas de producto clase `user_mission`. Las tres misiones standalone
agrupan 335 mensajes —232 de volumen, 87 de mute y 16 de status—; los 171
acreditados dejan 164 mensajes de esas tres misiones todavía fuera de este
corte. Además quedan composiciones.

La cadena probada es:

mensaje → parser conservador → `audio.volume`/`audio.mute` con intención durable,
o `audio.status` sin mutación → Core Audio `eRender`/`eMultimedia` → lectura
verificada → respuesta natural.

Release aprobó 665/665 pruebas .NET y la colección canónica mantuvo 59/59
pruebas Python más 148 subtests. El gate AOT físico de
`artifacts/product/audio_control_gate.json` verificó volumen, mute, replay sin
segundo efecto y restauración exacta en un equipo y un endpoint. Observa estado
de control, no sonido audible, y no amplía la trazabilidad a los 164 mensajes
restantes ni a otras operaciones del ledger.

## Trazabilidad ejecutada del séptimo corte

`tests/data/memory_corpus_oracle.json` liga cada caso a
`historical_messages.jsonl` y fija normalización NFC, whitespace colapsado y
casefold. Sus grupos ejecutables son:

| Ruta | IDs | Literales | Misiones | Fuentes |
|---|---:|---:|---:|---:|
| `memory.save` | 59 | 32 | 5 | 11 |
| `memory.recall` | 19 | 15 | 4 | 7 |
| `memory.forget` | 22 | 13 | 6 | 5 |
| unión positiva | 100 | 60 | — | — |
| `memory.correct` | 5 | 2 | 2 | 2 |
| negativos duros | 34 | 34 | 15 | 15 |

Los 44 casos canónicos cubren cada positivo y corrección una sola vez. Los
contratos adicionales fijan TTL, consentimiento e inspección; la ausencia de
una frase histórica de export queda declarada como requisito de producto, no
como cobertura inventada. Los negativos separan contexto conversacional,
secretos sin consentimiento, negación, otras operaciones y frases que no deben
producir una ruta standalone.

La cadena probada es:

mensaje → parser explícito → envelope privado ligado a identidad → confirmación
proporcional → `memory.*` → store DPAPI/AEAD → verificación → resultado privado
exitoso → proyección natural. Para export se añade escritura con contenido
sensible/secreto redactado y revalidación fresca del artefacto en cada replay.

Release aprobó 1.035/1.035 pruebas .NET y Python 65/65 más 157 subtests:
1.100 pruebas principales. Según la ejecución registrada, el smoke NativeAOT
verificó 21 capacidades/11 de memoria, DPAPI real, status, challenge/confirm de
enable, list vacío y rechazo de una raíz compartida. Se eliminaron helper/raíz
temporal; el output ignorado permanece en
`src/Baxy.Core/bin/.../native/baxy-core.exe`, sin artefacto versionado bajo
`artifacts/product`. Esto acredita la slice de memoria explícita; no prueba
que la memoria personalice otras operaciones, conversación general ni el resto
del ledger.

## Trazabilidad ejecutada del octavo corte

`tests/data/gpu_status_corpus_oracle.json` liga cada caso a
`historical_messages.jsonl`, conserva la misma normalización NFC/whitespace/
casefold y separa routing standalone de composiciones y falsos positivos:

| Ruta/frontera | IDs | Resultado esperado |
|---|---:|---|
| `system.status` / `gpu_identity` | 7 | identificar adaptadores/capacidades sin recopilar uso |
| `system.status` / `gpu_usage` | 19 | snapshot puntual de uso y memoria por adaptador |
| composiciones | 17 | no reducir una misión compuesta a consulta standalone |
| negativos duros | 34 | no enrutar conocimiento, web/precios, condicionales, historial, investigación, mutación o temperatura |
| universo seleccionado | **77** | 26 positivos + 51 fronteras fail-closed |

El inventario parte de 148 candidatos léxicos de producto: selecciona 74 y añade
tres colisiones de temperatura. No cierra el universo GPU ni el ledger. El
quinto corte conserva en paralelo su oráculo
113/113 de CPU/RAM/disco/batería/Windows; el nuevo routing no cambia esos casos
ni agrega GPU al summary genérico.

La cadena probada es:

mensaje → parser conservador → `system.status`/scope exacto → DXGI para
identidad + PDH para uso puntual → validación de consistencia → JSON interno
tipado → respuesta natural.

`nvidia-smi` se resuelve como alias natural de `gpu_usage`, no como herramienta:
la implementación no crea subprocess y la respuesta no afirma ejecución. Los
contratos también fijan que `gpu_identity` no recopila uso, que los campos de uso
aparecen los tres juntos y que un adaptador no medido queda ligado a un fallo
indexado en vez de recibir un cero inventado.

Release aprobó 1.209/1.209 pruebas .NET —37 Contracts, 44 Kernel, 232 Providers
y 896 integración— y Python 74/74. Una ejecución física managed y otra directa
NativeAOT observaron tres adaptadores, dos medidos y uno no disponible mediante
`unsupported` indexado. `scripts/test_gpu_status.ps1` convirtió esa ruta en una
compuerta reproducible: corroboró hello 21, identity/usage verificados, cero
fallos globales, correlaciones exactas, warmup `malformed_json`, stderr vacío y
exit 0. El binario mide 7.376.384 bytes y tiene SHA-256
`17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.
El artefacto sanitizado `artifacts/product/gpu_status_gate.json` usa schema
`baxy-gpu-status-gate-v1`. La compuerta no acredita temperatura, procesos,
hardware exhaustivo, perfil físico de 4 GB, GUI o instalación limpia.
