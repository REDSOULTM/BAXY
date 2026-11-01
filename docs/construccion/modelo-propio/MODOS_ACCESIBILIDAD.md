# Modos de accesibilidad: lo que existe y lo que falta (2026-10-18)

Lo pidió el autor como base de un objetivo futuro. No se implementa ningún modo nuevo sin su decisión. Hoy sólo está lista
la interacción por texto del modo estándar. La entrada por voz está en pruebas. «No vidente» y «Movilidad» se muestran
como «próximamente disponible» (Rail.tsx, commit db4af44f7).

Inventario de sólo lectura de la rama nb-proveedores. Las rutas son relativas a la raíz del repo.

## Común a los dos modos

### Entrada por voz (existe; sin pruebas unitarias; en vivo, a mano)

- **Cadena del micrófono:** `src/baxy_mind/voice.py`.
  - Wake word k4 en :131-141 y Parakeet Ultra en :122-128.
  - El corte de «Baxy» va por tiempo (:283-294) y los subtítulos en vivo, en :220-232.
  - Modos `wake` («escucho siempre») y `direct` (pulsar para hablar), en :74-91. Tras un pedido directo vuelve al modo
    anterior (:263-269).
- **Rutas de la App:** `src/Baxy.App/FieldProductChannel.cs:100-125` (`/voice/start`, `/voice/stop`, `/voice/trigger`,
  `/voice/release`).
- **Controles de la vista:** `src/Baxy.FieldUi/src/App.tsx`. Los modos del micrófono, en :300-324; pulsar para hablar,
  en :334-344; la barra espaciadora, en :399-401. En la bandeja, «Escuchar» (`Presentation/TrayMenu.xaml:99`).
- **De transcripción a turno:**
  - `MindSidecarClient.cs:761-767` recibe la transcripción.
  - `MainWindowViewModel.cs` `OnMindTranscript` la envía como `MissionInputSource.VoiceTranscript`, y desde ahí sigue el
    mismo camino que el texto.
  - Lo que se oye durante un turno se descarta, y ahora lo dice un aviso (commit e45a308ef).
- **Mientras BAXY habla, el micrófono se descarta** (voice.py:195): no se le puede interrumpir con la voz. Lo callan
  pulsar para hablar y escribir, y desde esta rama también una conversación nueva o silenciar la voz (449d92a12).
- **Un «sí» dicho a una confirmación** pasa por el modelo, no por una palabra fija:
  - `NativeTurnLoop.cs:182-196, 578-598`, `mind.py:353-362` y `ConfirmationAsk.cs:21`.
  - Nunca se ha probado por voz.
- **Evidencia del estado «en pruebas»:**
  - RENEW_TRASPASO.md:111-123 dice que se verificó con grabaciones del autor pasadas como si fueran el micrófono, y
    que falta la prueba en vivo con el micrófono.
  - :283-287 deja abierta la prueba `controls.spec.ts:92` (micrófono), que falla con la app recién arrancada.
  - Esta rama arregla una causa probable: el modo guardado ahora se aplica cuando la mente está lista (ef5b56879).

### Salida por voz (funciona, con pruebas)

- **Supertonic 3** en `src/baxy_mind/voice_output.py`, frase a frase y cancelable. Desde esta rama suena también la
  primera respuesta tras arrancar (E001, 26dcf5a38).
- **Qué se dice:**
  - Cada mensaje publicado de BAXY, es decir, la respuesta y la pregunta de confirmación (`MainWindowViewModel.cs`
    `AddMessageCore`).
  - El «Un momento.» tras un silencio (`SilenceNotice.cs`).
  - Nada durante el latido.
- **Los pasos no se dicen nunca.** StepStarted y StepCompleted sólo se ven como fichas en la vista. Ya existe una
  etiqueta legible de cada paso, «Título · destino» (`FieldStepProjection.cs:102-114`), que serviría para narrarlos.

### Control del escritorio y lectura (funciona; probado en Providers)

- **Teclado y ratón:** `input.key.press`, `input.text.type`, `input.pointer.control` (sólo clic en el sitio, centro o
  desplazamiento), `input.visible.click` (por etiqueta o índice) e `input.visible.controls`.
- **Ventanas:** `window.*`.
- **Navegador:** `browser.page.read`, `browser.tabs.list` y `browser.control` (`src/Baxy.Kernel/Operations/ProductCatalog.cs`).
- **Lo que oye una persona ciega:** la vista de pantalla es para el modelo (`ScreenViewProjection.cs:7-23`), así que la
  persona sólo oye el resumen del modelo.
- **Anuncios de foco:** no hay ninguno (falta un manejador de foco UIA y un aria-live).

### «Modo accesible» actual (sólo presentación)

- **Dónde está:** `PresentationModeStore.cs:9`, la ruta `/accessibility` y `system.settings.set accessible_mode`
  (`ProductCatalog.cs:1446-1461`).
- **Qué cambia:** texto y botones más grandes, contraste y contorno del foco (`App.tsx:237-240`, `styles/v4.css`). No
  cambia la conducta ni el audio.

## Modo 2, «No vidente»: lo que falta

- Narración hablada de cada paso.
- Un Sí/No fijo por voz para las confirmaciones.
- Interrumpir con la voz.
- Avisos sonoros de estado (escuchando, pensando, error).
- Anuncios de foco y de cambio de ventana.
- Una descripción de la ventana pensada para la persona.
- Releer en voz alta lo que BAXY escribió.
- La prueba en vivo con micrófono, y `controls.spec.ts:92` en verde.

## Modo 3, «Movilidad»: lo que falta

- Una primera configuración del micrófono sin manos.
- Seguir hablando sin repetir «Baxy».
- Encolar lo oído durante un turno, en vez de descartarlo.
- Un «para» o «cancela» hablado.
- Ratón por coordenadas o por rejilla.
- Órdenes de voz para los controles de BAXY (modo del micrófono, conversación nueva, reposo).
- La misma prueba en vivo con micrófono.
