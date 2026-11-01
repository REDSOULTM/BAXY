# Pendientes de la ronda 2 (computer use v3)

Integración `fable/cu-v3-ronda2` sobre `fable/cu-v3-ronda1`. `PROGRESO_V3.md` es del líder y queda en la versión de la
base; las notas de la integración viven aquí. Informes de las ramas: `%LOCALAPPDATA%\BAXY\cu-v3\r2c\<rama>.json`.

## Fusiones y conflictos

Orden: journal, molestia2, tooltip, familia, tipos-lectura, tipos-uia, arrastre (todas `--no-ff`).

- **familia** — `VisibleControlSurface.cs`: el `BoundWindow` de la base y el comentario nuevo del par de familia en
  `ForegroundIs`; se conservan los dos.
- **tipos-uia** — `DesktopUiaWorker.ps1`, despacho de comandos: `unnamed`/`tooltips` (tooltip) y `reveal` (tipos-uia).
- **arrastre** — por unión:
  - `DesktopUiaWorker.ps1`: `locate` junto a `reveal`, `unnamed` y `tooltips` (cabecera, funciones y despacho);
    `Parser.ParseFile` sin errores.
  - `ComputerUseMission.cs`: el registro del paso guarda `field/replace/consequence` y `from/to/toLabel/atX/atY/item`.
  - `computer_use.py`: `ACTS`, `STEP_PROMPT`, `STEP_GRAMMAR`, `_ACT_KEYS` y `_checked_act` llevan `reveal`, `type` con
    `field` y `drag`.
- Rojo de la fusión: `test_the_keys_the_mind_reads_are_the_shells_own` leía el primer enum del descriptor de
  `input.key.press`, que tras tipos-uia es `consequence`; ahora lee el de `key` (commit propio).

## Duplicados consolidados (ley 2)

- **Campo de formulario**: había dos vías. La determinista de tipos-lectura («poner X en V») hacía clic, `ctrl_a` y
  teclear, con el teclado y el frente. La del acto `type` con `field` de tipos-uia usa SetValue o EM_REPLACESEL, sin
  teclado. Queda una: `_form_field_arguments` (field + replace). Los homónimos («Horizontal» del tamaño y del sesgo)
  toman el primero en orden de lectura, igual en la mente (`_field_named`) y en la App (`LabelledField`; antes
  rechazaba con dos). Hay una sola constante de tipos de campo (`_FORM_FIELD_KINDS`).
- **Revelar en una lista**: el «mostrar X» determinista sólo giraba la rueda. Ahora pide primero `input.scroll` con
  `label` (UIA, sin rueda ni frente), lo mismo que el acto `reveal` (`_reveal_arguments`). La rueda queda sólo si el
  revelado por nombre falla.
- **Menú contextual**: una sola vía, la tecla `context_menu`/`shift_f10`. tipos-uia no creó otra. Se quitó del check
  `stepDone:input.context.menu`, una operación que no existe en el catálogo.
- **Teclas**: `missions.KEYS`, el enum de `ProductCatalog` y `VirtualKeys` del adaptador son tres capas
  (mente/kernel/provider), cruzadas por tests (KEYS ⊆ enum; cada tecla del enum es su acorde). Se quitó `f12` de
  `_KEY_WORDS`, que el shell no acepta.
- **Pasos encadenados**: `MAX_STEPS` de la mente y `maximumItems` del catálogo pasan ambos a 10, con un test que los
  fija iguales.
- Revisados sin duplicado:
  - Devolver el frente: `ForegroundHandBack.Return` usa `WindowsLeaseDesktop.GiveFront`, el mismo que el lease.
  - Pausa: un solo detector, `WindowsUserInputPause.Shared`.
  - Ventana quieta: `StaysStillAsync` (adaptador, hash de la superficie, espera de etiqueta) y `StillStarting` (misión,
    dos miradas en el arranque) miden cosas distintas en capas distintas.
  - `DrawingProcesses` (tooltip) frente a la familia (familia): procesos que dibujan dentro de la ventana frente a
    ventanas de nivel superior de descendientes.
- Duplicado anterior a esta ronda, no tocado: el baile `AttachThreadInput` de `VisibleControlSurface.BringToFront` y
  `WindowsLeaseDesktop.GiveFront` (el primero además anota `NoteFrontTaken`).

## Puntos extra

1. **Seguridad con `application` null.** No valía: la mente (`application_is_in_front` devuelve true sin
   aplicación) y la App (`BindToMissionWindow` sólo miraba con aplicación nombrada) dejaban actuar sobre VS Code
   delante. Ahora:
   - la vista marca `window.protected` por proceso (`VisibleControlSurface.ProtectedFrom(proceso, aplicación)`, la
     lista ya existente);
   - la mente para sin preguntar al modelo (`window_protected`);
   - `BindToMissionWindow` rechaza cualquier acto. Esto cubre también los pasos de un procedimiento aprendido, que no
     se olvida por eso;
   - la causa `computer_use_window_protected` se dice en palabras de la persona (operation_floor).
2. **MAX_STEPS = 10** con `maximumItems: 10`. Los tests del catálogo pasan de 8/9 a 10/11.
3. **Átomo `file:`**: exige que el archivo exista y que su última escritura sea posterior al inicio del sub-objetivo
   (`subgoalStartedUtc`; si no hay, el de la misión), con 2 s de holgura para sistemas de archivos de hora gruesa. Sin
   inicio no se cumple.

## Pendiente (para el líder)

- Nada de esta ronda se probó en vivo; todas las ramas encontraron `live.lock` puesto. Lista de casos en el informe.
- journal: el bloque de `cu_live.sh` de 9e1424087 (rama `fable/cu-universal-v3`) no está en esta base. Con la rotación
  del producto sobra: si se fusiona, quitarlo o subir su umbral por encima de 48 MiB.
- tipos-uia: `input.visible.reveal` e `input.context.menu` no son operaciones propias. Revelar es `input.scroll` con
  `label`; el menú, la tecla.
- tipos-lectura:
  - `split_request_clauses` sigue sin llamador.
  - Siguen sin leerse t-menu-1/2 (nombran la carpeta, no la app), t-long-4 y t-drag-1/2/4.
  - long-3 cabe ahora en 10 pasos; falta ver si se lee.
- arrastre: el destino de un archivo arrastrado no se comprueba con `file:`, porque la mente no conoce la ruta.
- molestia2:
  - `MolestiaPrimitivesLiveCheck` no ejercita `WatchHelperAsync`.
  - El texto dejado en el compositor se avisa pero no se borra.
- tooltip:
  - Los umbrales de la huella (6 celdas, ±24 de gris) están puestos a ojo.
  - La vista no lista los nombres aprendidos.
- familia: el rasgo (a) de la revisión («el marco no expone accionables») no se aplicó.
