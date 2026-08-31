# Goal 05 — la ejecución verificada

Cerrado el **2026-08-21**. Providers habilitados, efectos reales sobre
superficies que se dejaron como estaban.

> **El resultado en una línea:** lo que BAXY declara `completed` lo observó
> un verificador que no es el ejecutor. Un provider que informa éxito sin el
> estado reivindicado no consigue que BAXY diga «Listo». `pending` es sólo
> reintentable; un efecto externo ambiguo acaba en `failed` con
> `effectMayHaveOccurred` y el journal no lo vuelve a aplicar.

## 1. Dónde está la medición

| Qué | Ruta |
|---|---|
| Matriz | [`05_MATRIZ_EJECUCION.json`](05_MATRIZ_EJECUCION.json) |
| Pruebas del ejecutor que miente | `tests/Baxy.Integration.Tests/Goal05LyingExecutorTests.cs` |
| Estados terminales | `tests/Baxy.Kernel.Tests/Goal05TerminalStateTests.cs` |
| Matriz + Core JSONL en vivo | `tests/Baxy.Integration.Tests/Goal05CatalogExecutionMatrixTests.cs` |

Catálogo tipado: **170** operaciones (169 públicas + `app.status` interno).
**82** observadas de verdad. **88** no verificables, con razón.

## 2. Qué se cambió para que el ejecutor no sea el juez

- **`audio.volume` / `audio.mute`:** después del recibo del setter, Core lee
  `GetStatus` por separado y exige que el endpoint coincida con lo reivindicado
  (tolerancia 2 puntos de volumen; silencio exacto).
- **`note.create`:** ya decía `note.create.local.reopen.v1` y no reabría. Ahora
  relee el documento y falla cerrado si no está. Trash/update/restore igual.
- **`reminder.*` / `notification.dismiss` / `routine.*` mutantes:** releen el
  almacén (CAS) después de mutar; un `ILocalTaskStore`/`IRoutineStore` que
  devuelve un registro que no existe no completa.
- **`memory.save` y hermanas:** Recall/Status/Verify del export después de
  mutar; un store que guarda sin que Recall lo vea no completa.
- **`filesystem.write.text` y copias con SHA:** Hash independiente del recurso.
- **`clipboard.write.text`:** segunda lectura del texto.
- **Externas mutantes:** `Verified=true` sin `EffectObserved` no completa.
  Causa `external_effect_unobserved` o `external_effect_ambiguous`.
- No hay registro de estrategias ni bus de verificadores.
  `VerifierContractId` sigue siendo la identidad de catálogo.

## 3. El ejecutor que miente

Tres provocaciones sobre el handler enviado + `MissionEngine` desde
`operation.request`, dos veces cada una:

| Ejecutor | Observación independiente | Resultado |
|---|---|---|
| `SetVolume` reivindica el nivel pedido | `GetStatus` sigue en 55 % | `failed`, `verified=false`, `effectMayHaveOccurred=true`, el mensaje no empieza por «Listo» |
| Lanzador de Bloc de notas con PID inventado | `WindowsApplicationOpenVerifier` reabre el proceso | `failed`, `verified=false`, no «Listo» |
| `INoteStore.Create` devuelve un registro que no existe | `Read` por id | `failed`, `verification_failed` |

## 4. Estados terminales

| Caso | Status | Journal | Segunda ejecución del mismo `invocationId` |
|---|---|---|---|
| Fallo reintentable | `pending` | no asienta terminal | reentra el handler |
| Efecto ambiguo no reintentable | `failed` + `effectMayHaveOccurred` | asienta | replay, el handler no corre |
| `confirmation_required` | `pending` | no asienta | el token no autoriza otro `invocationId` |

## 5. Corrida en vivo (Core JSONL, dos veces)

Con `BAXY_DATA_DIR` aislado y providers reales. Restauración: volumen original,
portapapeles original, y `app.close` del Bloc de notas si esta sesión lo lanzó.

Completado y verificado en las dos vueltas: `audio.status`, `audio.volume`,
`note.create` + `note.read`, `app.open`, `app.status`, `app.installed`,
`system.time`, `system.identity`, `system.status`, `system.process.list`,
`network.status`, `window.active`, `window.resolve`,
`window.application.status`.

Una vez: `network.dns.status`, `network.ip.list`, `network.port.list`,
`app.close`, `clipboard.read.text` / `write.text` (restaurado),
`capture.screenshot` (BMP privado del data root).

`system.settings.status` falló con `brightness_status_verification_failed`:
WMI de brillo no corroboró dos lecturas. Queda en la lista de no verificables.

El almacén aislado (notas, CAS de ficheros, tareas) se observó por relectura
del documento, no por el retorno de `Create`.

## 6. Lo que no se puede verificar aquí

Las 88 filas `unverifiable` están en la matriz, cada una con su razón. Familias:

- **No restaurable:** `system.power`, wifi connect/disconnect, bluetooth pair/radio,
  vaciar papelera, matar proceso por nombre, instalar/comprar, imprimir/escanear.
- **Falta sesión o cuenta:** browser CDP, calendario, correo, oficina, Steam,
  WhatsApp/Discord, Netflix, web.search, SMTC.
- **SendInput / foco:** `input.*`, `clipboard.copy`/`paste` — Windows acepta el
  evento; eso no es el efecto semántico en la app enfocada, y dispararlo aquí
  escribiría en esta sesión.
- **Carpetas del usuario:** `filesystem.known.*`, `backup.known.*`, abrir
  Explorer.
- **API o entorno:** OCR sin `spa.traineddata`; brillo WMI que no corrobora;
  «está sonando esta pista» sin sesión SMTC.

Nada de eso se cuenta como pass. El degradado es honesto: BAXY no afirma el
efecto.

La matriz MVP externa (`actualEffectsExecuted=0`) sigue existiendo como
prueba de contrato (recibo no verificado → rechazo). **No es el pass de este
goal.**

## 7. Compuerta

`.\scripts\test_source_quality.ps1 -Mode Full` verde el 2026-08-21
(`source_quality_gate_passed: mode=Full`).

- .NET: Contracts 60, Integration 2780 pass / 1 skip, Kernel 132, Providers 442,
  Setup 477.
- Python: 8636 passed, 3 skipped, 446 subtests.

`py main.py` no se arrancó (producto de escritorio, sin browser).

## 8. Revalidación 09.5.11B (el cierre de arriba no se borra)

Las cifras de cierre (170/82/88, lying executor, terminales) siguen siendo el
cierre del 05. Holdout 09.5.11B reejecutó las suites dueñas dos veces
(Kernel 10/10, Integration Goal05+VoiceListen 46/46, 0 omitidas) y publicó
la matriz contemporánea en
`artifacts/goal095/revalidate/goal05_execution_matrix_goal09511b.json`:
**170** operaciones, **82** observadas, **88** no verificables (todas con
razón), 41 filas live, 40 completed+verified. El token de confirmación no
autoriza otro `invocationId`. Un ejecutor que miente no publica «Listo».
