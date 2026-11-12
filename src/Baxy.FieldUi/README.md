# BAXY FieldUi

FieldUi es la presentación React/TypeScript que `Baxy.App` muestra dentro de WebView2: el rediseño v4 con
lo que cambió en la v5 (`design_handoff_baxy`, ver [ORIGIN.md](ORIGIN.md)). No es una SPA desplegada, un servidor ni el backend de BAXY.

## Runtime

```text
Baxy.App (WPF)
  → WebView2 local (https://baxy.local, sin puerto ni red)
  → Baxy.FieldUi/dist
  → field-native-bridge.js        (fetch y WebSocket → mensajes baxy.field.v1)
  → FieldUiBridge.cs → FieldProductChannel.cs → MainWindowViewModel / NativeTurnLoop
```

La App bloquea la navegación externa, las ventanas nuevas y los requests de red arbitrarios. FieldUi no recibe
autoridad del sistema operativo y nunca habla directamente con Core, Mind o Providers.

## Regla de producto

La vista nunca afirma que algo se hizo si no se ejecutó y verificó. Todo lo que muestra llega del host:

| Lo que se ve | De dónde sale |
|---|---|
| Conversación, chips de paso y tarjetas Sí/No | `FieldTranscript` (el host la guarda; el evento `item` cambia un elemento, `transcript` la manda entera) |
| Estado de cada paso | `FieldStepProjection`, por la `verification` tipada del resultado: `ok` («Verificado») sólo si el efecto se releyó; `same` («Ya estaba así»), `sent` («Enviado, sin comprobar»), `read` («Leído»); `maybe`, `fail`, `skip` con su motivo |
| Título del paso y del catálogo | `Baxy.App/Assets/operation-labels.v1.json`, una entrada por operación del catálogo (se comprueba al arrancar) |
| «Salió a internet» y su registro | el efecto `network` del catálogo (`OperationEffects.Network`) de una llamada que llegó a su proveedor |
| Métricas del riel | `FieldTelemetrySampler`: CPU, GPU, temperatura (D3DKMT) y memoria de la mente y su llama-server; `—` si no se pudo leer |
| Arranque | piezas que la mente informa (`voice.status`: stt, wake, tts) y el modelo listo; sin porcentajes |
| Memoria, triggers, sesiones | la operación del chat por el kernel (`MemoryPanel`, `schedule.alarms`, `FieldSessionStore`) |

El tema, el tamaño de texto, el contraste, el perfil, el micrófono elegido y la pestaña de Ajustes son presentación
propia de la vista (`localStorage`); el resto de ajustes los guarda el host (`FieldSettings`, `ConfirmationModeStore`,
`PresentationModeStore`).

## Estructura

| Ruta | Rol |
|---|---|
| `index.html` | documento de entrada y script de escala (720p → 8K, nada a 0×0) |
| `src/App.tsx` | composición, estado derivado, anillo del borde, atajos y acciones |
| `src/store.ts` | socket `/events` y reducer de eventos |
| `src/lip.ts` | línea de tiempo de la voz (evento `lip`) para la boca del avatar |
| `src/api.ts`, `src/types.ts` | rutas del host y contrato visible |
| `src/components/` | riel, chat, subtítulos y arranque, entrada y micrófono, avatar en vídeo (`AvatarVid`), cara y red (`face/`), cosmos |
| `public/` | clips del avatar (`clips/`), fondos de nebulosa (`bg/`) y favicon; `vite build` los copia a `dist/` |
| `src/components/panels/` | memoria, qué puedo hacer, sesiones, triggers, propuestas, ajustes |
| `src/styles/` | fuentes y la cascada del diseño (`base` → `baxy` → `v4`) más `shell.css` |
| `e2e/` | pruebas con Playwright: las de la vista sin la app (`pnpm test`) y la aceptación contra la app real |
| `dist/` | payload servido por la App (versionado: lo empaqueta `Baxy.Setup`) |

## Preparar, validar y construir

Desde esta carpeta:

```powershell
pnpm install --frozen-lockfile
.\node_modules\.bin\eslint.cmd . --max-warnings 0
.\node_modules\.bin\tsc.cmd --noEmit --incremental false --pretty false -p .\tsconfig.app.json
pnpm build
```

`pnpm build` regenera `dist/`, que se versiona: un cambio de la vista se entrega con su `dist/`.

`pnpm dev` no sirve para ver la interfaz: sin `field-native-bridge.js` no hay rutas ni `/events`.

## Pruebas de la vista sin la app

```powershell
pnpm test
```

Corre el proyecto `vista` de `playwright.config.ts`: todas las specs de `e2e/` que no se enganchan a la ventana de BAXY
(las que no importan `attach` de `e2e/app.ts`). No necesitan la app, el modelo ni la GPU: importan los módulos de la
vista, o la abren en un navegador sin ventana, sola (`e2e/headless.ts`: el Chromium de Playwright) o contra el anfitrión
de prueba `e2e/host.ts` (Edge; `BAXY_TEST_BROWSER` nombra otro), que contesta las rutas del host y su `/events`. Ahí están `view.spec.ts` (lo que la persona toca,
con un host que acepta, rechaza o no contesta), la lógica (`logic`, `a11y-logic`, `avatar-*`) y `layout-view.spec.ts`
(la disposición en 11 tamaños, las mismas comprobaciones que la aceptación hace sobre la ventana real). Van siempre
enteras: una spec nueva entra sola en `vista` o en `app`.

## Aceptación

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\scripts\test_field_ui.ps1
```

Lanza BAXY con el puerto de depuración de WebView2 y corre `e2e/` entero (los proyectos `vista` y `app`; sólo las
de la ventana real: `playwright test --project=app`): escala, cielo, red y bocas; humo en 11 tamaños
de 720p a 8K (marco lleno, nada fuera, ningún texto cortado, texto ≥ 7 px, lienzos dentro de su tope, cara
centrada, chat plegado 12 veces sin línea de puntos, Ajustes cabe); arranque con la ventana a 0×0 y cambio de tamaño
en vivo; `avatar.spec.ts`: el vídeo calza con la red viva, rota sin repetir, sigue al estado en turnos reales y
en la tarjeta Sí/No, se duerme y despierta con transición, y `?avatar=live` dibuja la cara; `lipsync.spec.ts`:
la boca contra el sonido de BAXY (`scripts/tools/loopcap`, loopback de proceso, con ruido de fondo sonando); y `controls.spec.ts`: cada control reversible (ajustes, micrófono en sus tres modos, rail, paneles, chat y
ventana) se pulsa, se lee el host por sus rutas para ver que cambió de verdad y se deja como estaba. Con BAXY ya
abierto con el puerto: `-NoLaunch`.
