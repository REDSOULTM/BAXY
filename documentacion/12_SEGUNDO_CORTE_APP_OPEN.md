# Segundo corte productivo: `app.open` acotado

Estado: implementado y auditado en el commit `9c67495d5839`; pruebas
automatizadas aprobadas. La aceptación física quedó **omitida**, no aprobada,
porque ya existía una instancia de Bloc de notas. Este corte no cierra ningún
Must adicional ni los bloqueantes B-004/B-005/B-006.

Nota histórica: las métricas y el build de este documento pertenecen al
checkpoint anterior a `documentacion/13_TERCER_CORTE_NOTAS_NATURALES.md`; no
son la corrida vigente ni contienen el tercer corte.

## Alcance exacto

El catálogo del core pasa de seis a siete operaciones al incorporar
`app.open`. El único destino permitido es el identificador constante
`windows.notepad`.

La entrada natural acepta órdenes directas y preguntas corteses acotadas para
abrir Notepad/Bloc de notas. No convierte en efecto rutas, argumentos, URLs,
metacaracteres, órdenes múltiples, negaciones, preguntas de estado, preguntas
de procedimiento ni nombres de otras aplicaciones.

En el ledger vigente, el corte cubre 13 registros históricos agrupados en
siete literales sin distinguir mayúsculas. Todos pertenecen a
`mission_user_mission_app_open_722f2ee554`, cuya prueba es
`hist_8a2c7052a17943`. Esa misión reúne 163 mensajes con otros destinos, casos
inexistentes y composiciones; por tanto permanece solo parcialmente cubierta.

## Ejecución y verificación

- El handler del core exige riesgo `low_reversible`, `appId` exacto y un recibo
  ligado a la misma invocación, aplicación, PID, creación, ruta, ventana y
  modo de apertura/reutilización. Cualquier contradicción falla como
  `verification_failed`.
- El provider inventaría primero y falla cerrado si no puede descartar un
  duplicado. Solo acepta el Notepad canónico de System32 o el paquete Microsoft
  cuya familia, nombre completo, arquitectura, ruta y cadena sin reparse
  coinciden exactamente.
- El lanzamiento usa `CreateProcessW` sin argumentos ni handles heredados. El
  core sigue dentro de un Job con `KILL_ON_JOB_CLOSE`; únicamente el bootstrap
  permitido solicita `CREATE_BREAKAWAY_FROM_JOB`, para que la aplicación
  solicitada sobreviva al cierre del core.
- El foco se solicita al PID exacto. Un verificador independiente reabre el
  proceso y vuelve a observar identidad, hora de creación, HWND, visibilidad y
  primer plano antes de permitir una respuesta de éxito.
- Cada invocación conserva un intent/recibo JSON con checksum SHA-256,
  escritura atómica y topes de 16.384 entradas/64 MiB. El checksum detecta
  corrupción accidental; no es HMAC.
- El replay es conservador y at-most-once por `invocationId`: después de un
  estado ambiguo o un PID desaparecido no vuelve a lanzar. Informa que el
  efecto pudo ocurrir; una orden posterior usa otra identidad y vuelve a
  inventariar.

## Evidencia automatizada

| Evidencia | Resultado |
|---|---|
| Suite .NET Release | 230/230: Contracts 23, Kernel 26, provider 56, integración 125 |
| Suite Python tras la revisión del corpus | 59/59 |
| Snapshot conjunto previo al tercer corte | 289 pruebas |
| Auditoría adversarial final | PASS; cero P0/P1 pendientes |
| Build local | 14 archivos de carga, 50.546.916 bytes, más el manifiesto |
| SHA-256 de `Baxy.exe` | `a531f1c90d401c7277d1ee63cd1eee29ecfe1cca664efbddd50b168425c08e0c` |
| SHA-256 de `baxy-core.exe` | `e9a7a3939066279eb397aa21967b6f5ae08f7fc266aa71b27f21b39892c98d51` |
| Captura de notas | 980×680; `core_ready=true`, `mission_completed=true`, una nota |

La captura `artifacts/product/product_notes_slice.png` vuelve a comprobar el
flujo de notas sobre el build de ese checkpoint. No es evidencia visual de
`app.open`.

## Gate físico

`artifacts/product/app_open_gate.json` registra `status=skipped`,
`reason=preexisting_notepad` y código 2. Detectó una sola instancia
preexistente, PID 5472, y la preservó. En consecuencia permanecen en `false`:

- lanzamiento fresco;
- replay físico sin instancia adicional;
- supervivencia tras cerrar core/Job;
- recorrido GUI extremo a extremo.

El gate arranca `baxy-core.exe` directamente dentro de un Job equivalente. No
atraviesa físicamente el parser WPF ni el `CoreProcessClient`; esas fronteras
solo están cubiertas por pruebas automatizadas. Además, el gate ya no cierra
Notepad por defecto ni usa terminación forzada. Un cierre normal requiere el
switch explícito para una sesión de prueba quiescente.

## Revisión semántica v2 del corpus

La errata quedó cerrada mediante regeneración conjunta de mensajes, misiones y
mapping. El cutoff y las 122.744 ocurrencias permanecen intactos; el particionado
por alcance produce 14.836 `message_id` —12.036 de producto y 2.800 de traza—.
`app.open` queda canónicamente en 329 filas, 98 mensajes conservan sus efectos
denegados y el ledger se reagrupa en 2.083 misiones. Dos reconstrucciones A/B
produjeron los cuatro artefactos byte a byte idénticos y 36/36 pruebas de
contrato específicas del corpus aprobaron.

La revisión no cambia los 13 registros que reconoce el parser acotado ni amplía
el runtime. El alcance funcional 1.0 es español, inglés y spanglish; ejemplos
inequívocamente ajenos permanecen solo para trazabilidad histórica.

## Estado de producto

El progreso permanece en **5/15 Must (33,3 %)**. B-004 sigue abierto porque
BAXY 1.0 requiere más operaciones, composición y conversación; B-006 sigue
abierto porque el gate físico fue omitido. El build continúa siendo un
directorio ejecutable local, no MSI/MSIX ni instalación limpia.
