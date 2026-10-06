# ADR-0008 — Restauración literal de BAXY Field

- Estado: **Aceptado**.
- Fecha: 2026-07-16.
- Ámbito: presentación de escritorio; no cambia la autoridad del core, el
  planner ni la frontera de voz.
- Sustituye: solo la elección de presentación WPF pura de ADR-0001. Conserva
  su host .NET, lifecycle, core NativeAOT, JSONL y Job Object.

## Contexto

El usuario pidió reemplazar la presentación reconstruida por la GUI que BAXY
usaba antes. Git conserva esa interfaz completa en `4a83f2d`, y la referencia
visual coincide con esa revisión: `triggers/tools` a la izquierda,
`sessions/memory` a la derecha y el campo neuronal en el centro. Las revisiones
posteriores agregaron superficies que no aparecen en la referencia.

Reimplementar la imagen en XAML habría creado una tercera GUI y perdido el
comportamiento original. Restaurar todo el backend Python antiguo habría
reintroducido autoridades, tools y contratos ya sustituidos.

## Decisión

1. `src/Baxy.FieldUi` contiene los 39 archivos visuales exportados literalmente
   de `4a83f2d082d6b0fec8297e801b96a0da620b059e`.
2. Los dos archivos de build omitidos por aquel commit se recuperan, también
   literalmente, de `63843e4` y se identifican en `ORIGIN.md`.
3. `Baxy.App` continúa siendo el host .NET 10 WPF y dueño del core/mind. Su
   única superficie es un WebView2 local que sirve el `dist/` congelado mediante
   un virtual host; no abre un servidor HTTP ni un puerto loopback.
4. Un bridge inyectado antes del documento adapta `fetch`, WebSocket y los
   controles históricos de ventana a mensajes nativos tipados. Texto y voz
   vuelven a confluir en `MissionInput`; el planner y el core conservan toda la
   autoridad.
5. Navegaciones, ventanas nuevas, requests web externos y ejecución JSON directa
   de tools quedan bloqueados. Memoria privada y rutinas arbitrarias continúan
   exigiendo el chat/planner actual; la GUI no recupera las autoridades directas
   del backend antiguo.
6. CPU, RAM, disco y GPU visibles se leen de los providers Windows actuales.
   Red y temperatura aparecen como no disponibles, no como mediciones inventadas.

## Evidencia

- 39/39 blobs exportados coincidieron con el tree de Git.
- Digest ordinal conjunto: `A05524E37A8E52AF7F6CE0A42E5988A814ED169F42A23DD95B4DB811B81761CF`.
- El source histórico compila con React/Vite después de recuperar sus dos
  archivos de build; el producto conserva el `dist/` original, cuyos tres
  SHA-256 están fijados por tests.
- El host compiló sin warnings y la ventana física mostró el shell original,
  telemetría local, actividad, transición `Thinking → Idle`, texto por el motor
  actual y wake/voz sincronizados.

## Consecuencias

- Se recupera la GUI exacta solicitada sin portar el monolito antiguo.
- WebView2 vuelve a ser una dependencia del shell y consume más recursos que la
  presentación WPF pura. La página no puede hacer red externa, pero el runtime
  WebView2 debe seguir midiéndose como dependencia de Windows.
- La accesibilidad deja de depender de los AutomationIds XAML anteriores. El
  frontend conserva HTML semántico, pero Narrator/NVDA y DPI físico requieren
  una nueva pasada; la evidencia UIA del shell WPF anterior queda histórica.
- Adjuntos del compositor histórico permanecen visibles, pero el bridge los
  rechaza con `501` porque `MissionInput` actual aún no tiene un contrato de
  adjuntos. No se finge soporte.

## Fallback y reapertura

El fallback es la presentación WPF previa en `f51c7c3`; core, mente, stores y
protocolos no necesitan rollback. Reabrir si WebView2 realiza tráfico no
aceptable, si el renderer no se recupera, si falla el gate accesible o si se
define un contrato tipado de adjuntos que permita cerrar la única degradación
visible del compositor.

## Reapertura acotada — 2026-08-11

La revisión física del MVP autorizada por el usuario detectó que la barra de
título y `about` seguían mostrando “gemma 4” aunque el runtime activo era BAXY
con Qwen 3. El source React histórico permanece intacto: una superposición
acotada del puente nativo corrige identidad, texto diagnóstico y ancho de
ajustes. También oculta pestañas históricas sin respaldo nativo y vuelve de
solo lectura los diagnósticos restantes, porque el host no admite el PUT
histórico. El layout, el aislamiento de WebView2, el contrato `baxy.field.v1` y
las autoridades permanecen intactos. El build deliberado conservó los bundles
JS/CSS y sólo normalizó el formato de `dist/index.html`; la procedencia y el
nuevo digest están en `src/Baxy.FieldUi/ORIGIN.md`.

## Reapertura de recursos — 2026-08-31

Goal 10.2.5 demostró que dos bucles visuales reconciliaban o escribían estilos a
la frecuencia completa del monitor durante el reposo. Se conserva toda la
semántica visual y sus velocidades temporales, pero los RAF permanentes se
sustituyen por schedulers que duermen: 4 Hz en reposo, 30 Hz durante conversación
y 1 Hz sin render oculto, además de la suspensión nativa. No cambian
layout, bridge, autoridad, red ni navegación. `dist/` se regeneró de forma
deliberada con el grafo fijado; los hashes vigentes quedan en `ORIGIN.md`.

## Reapertura de progreso — 2026-09-07

C03 UI102 demuestra que el aviso generado llega antes del final, pero el lector
lo coloca en el placeholder del input todavía ocupado por la petición. Se mueve
la etiqueta a una región `role=status` encima del input, usando el mismo estado
React y su borrado al completar. Se conserva el borrador y se retira su uso como
placeholder de progreso. No se añade otro lector en el bridge ni otra autoridad.
Source y dist se regeneran deliberadamente como unidad; el sello se actualiza en
ORIGIN.md y MainWindowShellContractTests. La comprobación física antes/después y
sus límites se conservan en los informes UI102 y tramo103 de C03.

## Reapertura de error de composición — 2026-09-07

C03 UI107 observa un fallo total real del servidor: la cola agota sus intentos,
pero el grafo vuelve a Idle y la actividad muestra un código interno. El estado
tipado `error` proyecta HasCompositionError desde la App y se conserva también
al conectar el lector; la cola pendiente proyecta thinking sin bloquear entrada.
El lector React existente consume state sin añadir otro canal o autoridad.
Error/Response error son etiquetas de estado de interfaz, no una respuesta de
BAXY ni una explicación generada. El diagnóstico composition_failed conserva
causa/ruta en su evento tipado y deja de duplicarse como texto de conversación.
Una región alert persistente identifica el error sin mover foco; se conserva
la posibilidad de una nueva petición. No se reejecutan efectos automáticamente.
Source/dist y sello se regeneran deliberadamente; ORIGIN registra las huellas.
