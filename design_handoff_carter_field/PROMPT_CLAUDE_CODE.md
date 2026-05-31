# PROMPT PARA CLAUDE CODE — Rediseño de GUI de Carter (gemma 4 · field)

> ⚠️ **ESTO ES SOLO UN CAMBIO DE INTERFAZ (RESKIN).**
> NO toques la lógica, el backend, el agente, los tools, el WebSocket, el manejo de estado real, la voz, ni nada funcional.
> SOLO cambia el **aspecto visual** (HTML/JSX/CSS de la GUI) para que se vea EXACTAMENTE como el prototipo en `prototype/`.
> Mantén intacto TODO lo que la app ya hace; solo reemplaza la capa de presentación.

---

## Qué tienes que hacer

Tengo una app de escritorio (cliente de un agente local "gemma 4"). Acabo de rediseñar su interfaz por completo. En la carpeta `prototype/` está el rediseño terminado y funcionando (HTML + React vía Babel + CSS). 

Tu tarea: **portar ese aspecto visual a mi app real**, respetando su arquitectura y conservando toda la funcionalidad existente. Donde mi app ya conecta datos reales (métricas, log de actividad, estado del agente, settings, etc.), debes **mantener esas conexiones** y solo cambiar cómo se ven. El prototipo usa datos simulados (mocks) únicamente para demostrar el aspecto y las animaciones — en mi app esos datos vienen del backend real y deben seguir viniendo de ahí.

Reproduce el diseño **al pie de la letra**: colores, tipografías, tamaños, espaciados, animaciones, tiempos, estados y comportamiento visual. Usa los archivos de `prototype/` como fuente de verdad exacta (ábrelos y léelos).

---

## Resumen de la interfaz (para que no te pierdas)

Es un **instrumento compacto y centrado** (ventana de ~1040×600 px) sobre fondo casi negro azulado, con una **luz roja que viaja girando por el contorno**. Tres columnas:

```
┌──────────────────────────────────────────────────────────────┐  ← borde con luz roja viajera
│ IZQUIERDA 200px │   CENTRO (fluido)        │ DERECHA 300px    │
│                 │                          │                  │
│ gemma 4         │     [grafo neuronal      │ + ? ⚙settings    │
│ 7.2b · local    │      con núcleo          │ activity  #id    │
│                 │      brillante al        │ ┌──────────────┐ │
│ ⏻ online        │      centro, neuronas    │ │ log entries  │ │
│                 │      orbitando, luz      │ │ (scroll)     │ │
│ system    38%   │      viajando por las    │ │ ts · TAG     │ │
│ cpu 42%  ▔▔▔▔   │      conexiones]         │ │ mensaje...   │ │
│ mem 13gb ▔▔▔    │                          │ └──────────────┘ │
│ gpu 33%  ▔▔     │      "Idle" (estado)     │                  │
│ net 6mb  ▔▔▔    │                          │ [sessions][memory]│
│ dsk 38%  ▔▔     │   › ask, instruct...  🎙✎→│                  │
│ tmp 61°  ▔▔▔    │   (no attachments)       │ local·no telemetry│
│                 │                          │                  │
│ perfil          │                          │                  │
│ 👤 normal       │                          │                  │
│ 👁 no vidente   │                          │                  │
│ ♿ movilidad    │                          │                  │
│                 │                          │                  │
│ ctx 15k ▔▔▔     │                          │                  │
│ [triggers][tools]│                         │                  │
└──────────────────────────────────────────────────────────────┘
```

### Columna IZQUIERDA (200px) — substrate
- **Header**: logomark (8 puntitos que se reordenan al cambiar de estado) + "gemma 4" + subtítulo "7.2b · local".
- **Toggle ⏻ online / standby**: enciende/apaga el agente. En standby todo el campo se apaga (ver más abajo).
- **Métricas del sistema**: cpu, mem, gpu, net, dsk, tmp. Cada una: etiqueta + valor compacto ("cpu 42%") y debajo una **barra fina full-width** rellenada según el %. A la derecha del título "system" va el % global.
- **Perfil de accesibilidad** (3 filas con ícono): normal (persona), no vidente (ojo tachado), movilidad (silla de ruedas). La activa tiene borde y barra lateral de acento.
- **ctx**: barra de presupuesto de contexto ("15.7k / 34.0k").
- **2 cajas** abajo: triggers, tools (alineadas al fondo).

### Columna CENTRO (fluida) — el campo (FOCO PRINCIPAL)
Visualización SVG animada con capas (de atrás hacia adelante):
1. **Nebulosa** (bandas onduladas translúcidas que contra-rotan lento).
2. **Campo de estrellas** (~300 puntos) que **rota lento como una galaxia**.
3. **Aristas** de la malla neuronal (líneas finas; las del último turno quedan brillando ~5s).
4. **Líneas punteadas** desde los nodos internos hacia el núcleo.
5. **Anillo orbital** de ~64 partículas girando alrededor del núcleo.
6. **NÚCLEO central** grande y brillante (halo + disco + núcleo + píxel caliente que pulsa) con la etiqueta del estado debajo ("Idle"/"Thinking"/etc., grande).
7. **Nodos** de la malla: 26 nodos, 6 son hubs etiquetados (context, router, agent, tools, memory, voice).
8. **Pulsos de señal** que viajan por las aristas dejando una **estela** (cometa).
9. **TRACER**: al pensar, un pulso grande color marfil recorre el camino voice→router→context→memory→agent→tools→voice.
- Abajo: **input de chat** (chevron › + texto "ask, instruct, or paste" + contador de tokens + botones 🎙 micrófono / ✎ adjuntar / → enviar). Debajo, fila de adjuntos ("no attachments" o pills de archivos).

### Columna DERECHA (300px) — activity
- **Toolbar arriba**: `+` (nueva sesión), `?` (atajos), **`⚙ settings`** (botón con texto, en rojo).
- **Header**: "activity   N entries · #id".
- **Log de actividad** (scroll): cada entrada = timestamp (mono) + TAG en MAYÚSCULAS coloreado + mensaje. Tags: TOOL, YOU, GEMMA, MEMORY, TRIGGER, BOOT, THOUGHT, SYSTEM, CONTEXT.
- **2 cajas** abajo: sessions, memory.
- **Footer**: "local · no telemetry" + reloj.

### Panel de SETTINGS (modal)
Modal con 11 pestañas: connection, agent, sampling, behaviour, transcript, voice, profiles, toggles, paths, prompt, about. Cada una con sus campos (inputs, números, textareas, checkboxes, browse, tips). Footer: "restart agent" (izq) · "cancel / apply" (der). **Conecta estos campos a tu config real** (en mi app probablemente leen/escriben el mismo archivo de configuración que ya usas).

---

## Estados del agente (¡crítico para el aspecto!)

La app tiene 5 estados visuales. **Casi todo el color cambia con el estado.** Conecta esto a los eventos REALES de tu agente (no al mock de setTimeout del prototipo):

| Estado | Cuándo | Núcleo / neuronas / borde viajero | "Cromo" (online, perfiles, settings, mic, input, cajas, tags del log) | Barras de métricas |
|---|---|---|---|---|
| **standby** | apagado (toggle off) | gris · **borde se DETIENE**, neuronas **desaparecen** (fade) | rojo (reposo) | gris |
| **idle** | encendido, en reposo | **rojo** | **rojo** (color original/reposo) | azul (contraste) |
| **listening** | capturando voz | rojo brillante | teal (contraste) | teal |
| **thinking** | razonando | **azul** | dorado (contraste) | dorado |
| **speaking** | respondiendo | **dorado** | azul-violeta (contraste) | azul-violeta |

**Reglas de color (importantísimas, las pulimos mucho):**
- El **núcleo, las neuronas, el contorno viajero y la etiqueta de estado** toman el color del estado.
- El **"cromo"** (toggle online, perfiles, settings, micrófono, línea del input, cajas activas, tags del log) está en **rojo cuando está en reposo (idle/standby)** y solo toma el **color de CONTRASTE** durante los estados activos (listening/thinking/speaking), y **vuelve al rojo** al terminar.
- Las **barras de métricas** siempre usan el color de **contraste** del estado (nunca el mismo color del estado).
- El tag **YOU** del log siempre queda en blanco hueso (es el usuario), el resto sigue el acento.

**Transiciones de power (toggle online/standby):**
- Al pasar a **standby**: la luz del borde **decelera suavemente hasta detenerse** y las neuronas **se desvanecen** (fade-out visible).
- Al volver a **online**: la luz del borde **arranca y acelera** progresivamente hasta su velocidad normal (no de golpe), y las neuronas **reaparecen** (fade-in).

---

## Tokens de diseño (exactos)

**Colores**
```
Fondos:    #0A0E14 base · #0F1419 panel · #161B22 elevado · #1F2733 divisores
Prussian:  #2E4BA0 · #1B2A5E · #5B7FDB · edges #2A3550
Carmesí:   #B83A4A (acento/rojo base) · #7A1E2B · #E55366 · #F5C6CC
Texto:     #D8DCE6 bone · #8B95A8 segundo · #5B6580 muted · #3F4860 dim
Estados (núcleo):  standby gris #5B6580 · idle/listening rojo · thinking #2E4BA0 · speaking #C9A66B
Contraste por estado (cromo activo + barras):
   idle→#5B7FDB · listening→#6FA8B0 · thinking→#C9A66B · speaking→#7B95D9 · standby→#5B6580
```
**NUNCA**: cian, neón, blanco puro #FFFFFF (salvo el píxel del núcleo/tracer), verdes saturados, sombras drop fuertes.

**Tipografía**: Inter (400/500) + JetBrains Mono (400/500, para números/timestamps/tokens). Tamaños 9–18px (escala compacta). Pesos 400/500, **nunca 700+**. Mayúsculas SOLO en los tags del log. `font-feature-settings: "tnum"` en todos los números.

**Layout**: ventana centrada `min(1040px,100%) × min(600px,100%)`, borde redondeado 5px, columnas `200px / 1fr / 300px`. Radios 2px. Sin barra superior ni inferior (se eliminaron).

**Motion**: fade 240ms · hover 120ms · logomark 600ms cubic-bezier(.4,1.4,.5,1) · pulso núcleo sine 0.8–3.4Hz · órbita 1.5–22°/s · galaxia 0.15–1.20°/s · pulsos 1.1–2.2s por arista · tracer 5s ease-in-out · recolor de acentos 700ms.

---

## Cómo conectar con lo real (NO uses los mocks)

El prototipo simula todo con `useState`/`setTimeout`/`useDriftingMetric`. En mi app, **reemplaza cada mock por la fuente real** que ya existe:
- `convState` ← eventos reales del agente (idle/listening/thinking/speaking) + el toggle de power para standby.
- Métricas cpu/mem/gpu/net/dsk/tmp ← tu monitor de sistema real.
- Log de actividad ← tu stream/log real de eventos del agente (mismo formato: timestamp, tag, mensaje).
- Tokens / ctx ← del runtime real.
- Settings ← leer/escribir tu archivo de configuración real (el mismo que ya usa la app).
- Toggle online/standby ← debe efectivamente pausar/reanudar el agente como ya lo hace.

Si mi app es PyQt/otra tecnología y no React: recrea el MISMO aspecto y comportamiento con los widgets/canvas de esa tecnología (el grafo se puede hacer con canvas/QML/SVG). Lo que importa es que **se vea y se comporte idéntico**, sin perder funcionalidad.

---

## Archivos de referencia (en `prototype/`)
```
index.html              · entrada; orden de carga de scripts (React+Babel pinneados)
styles.css              · TODOS los estilos + tokens arriba
app.jsx                 · App raíz, estados, animación del borde, recolor por estado, mocks a reemplazar
components/icons.jsx     · set de íconos SVG (incluye person, eye-off, wheelchair, power, mic, settings…)
components/cluster.jsx   · LogoMark (animado por estado) + ParticleCluster
components/substrate.jsx · columna izquierda
components/graph.jsx     · NeuralGraph: estrellas, nebulosa, núcleo, órbita, pulsos, tracer, fade de neuronas
components/field.jsx     · columna centro (grafo + input)
components/activity.jsx  · columna derecha (log + cajas + toolbar)
components/panels.jsx    · panel de sesiones (chrome de modal)
components/settings-panel.jsx · panel de settings con 11 pestañas
```
Para previsualizar el rediseño: abre `prototype/index.html` en un navegador.

---

## Checklist de aceptación
- [ ] Se ve **idéntico** al prototipo (colores, tipos, espaciados, animaciones).
- [ ] Los 5 estados cambian los colores como en la tabla (núcleo=estado, cromo=rojo en reposo / contraste en activo, barras=contraste).
- [ ] Toggle online/standby: borde frena + neuronas desaparecen; al volver, borde acelera + neuronas reaparecen.
- [ ] Luz roja viajando por el contorno (color según estado).
- [ ] **Toda la funcionalidad anterior de la app sigue funcionando igual** (solo cambió el aspecto).
- [ ] Settings conectado a la config real; log conectado a eventos reales; métricas reales.

**Recordatorio final: esto es SOLO un cambio de interfaz. No elimines ni rompas ninguna funcionalidad. Solo cambia cómo se ve.**
