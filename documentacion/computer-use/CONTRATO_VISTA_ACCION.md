# Computer use — contrato de vista y acción

Fase 4 del plan post-goal C03 (`artifacts/comprobaciones/C03/PLAN_POSTGOAL_2026-09-20.md`),
decisiones D10, D15, D16, D21, D23 y D24 (`DECISIONES_DUENO_2026-09-20.md`). Todo el
motor se construye sobre este contrato: lo que el modelo ve, lo que puede hacer, cómo
se verifica cada acto y cuándo termina una misión. Nada de lo que sigue conoce una
aplicación concreta.

Principios que manda la identidad (`documentacion/00_IDENTIDAD.md` §«El catálogo», §«Peligro
y confirmación») y el diseño medido (`artifacts/comprobaciones/C03/COMPUTER_USE_DISENO.md`
§1–§4, §10):

1. **Los ojos son el árbol de accesibilidad, no la captura.** La mente es Qwen3-4B de texto,
   4096 de contexto, temperatura 0. Ve una vista compacta: texto, nunca píxeles.
2. **Un solo acto por paso, nombrado.** El repertorio es cerrado y cada primitiva lleva su
   postlectura; un clic sólo cuenta si la superficie cambió, el control desapareció o quedó
   seleccionado.
3. **El bucle es mirar → elegir un acto → ejecutarlo con verificación → volver a mirar.**
   Termina por comprobación de éxito, por presupuesto o porque la vista no cambia.
4. **La mente propone, el Kernel autoriza, el provider ejecuta.** Cada paso es una operación
   del catálogo en el journal, con el riesgo de su primitiva (`RiskPolicy`, modo normal: sólo
   confirma lo destructivo o lo que llega a una persona).
5. **Cero código por aplicación fuera de alias.** Lo que distingue apps son etiquetas leídas
   en pantalla y el catálogo de aplicaciones instaladas; nada más.

---

## 1. La vista compacta (`input.visible.controls`, v2)

Operación de sólo lectura, ya existente, que pasa de «lista de nombres» a **vista
compacta**: lo que una persona ve en la ventana de delante, en texto, en ≤ 60 controles.
Contrato de verificación `input.visible.controls.windows.uia.snapshot.v2`.

### 1.1 Argumentos

```json
{
  "limit": 60,            // opcional, 1..60; por defecto 60
  "includeText": true,    // opcional; añade el texto OCR por zonas (cuesta ~1 s)
  "waitForLabel": "Biblioteca", // opcional; espera acotada (≤ 24 s) hasta que esa etiqueta
                                // aparezca en controles o texto antes de devolver la vista
  "processId": 1234,            // opcional; la ventana de ese proceso (o el marco que la aloja,
                                // UWP) es la superficie aunque otra tenga el foco: es la app
                                // que la misión acaba de abrir. Se trae al frente.
  "application": "Configuración" // opcional; sin processId, la ventana visible cuyo título
                                // contiene ese nombre (plegado: minúsculas sin tildes) es la
                                // superficie y se trae al frente. La categoría «navegador» /
                                // «browser» es la ventana delantera del navegador predeterminado
                                // de la persona (UserBrowser*), aunque haya processId. Sin
                                // ninguna, la ventana en primer plano.
}
```

Si otro proceso dibuja sobre el centro de la ventana elegida (un reproductor a pantalla
completa, un panel del sistema), la vista intenta una vez traerla al frente y, si sigue
tapada, la devuelve igual con `window.coveredBy {title, process}`: lo leído es la ventana
pedida, pero un clic caería sobre la que la tapa. La misión se detiene con
`computer_use_window_covered` y lo dice con el título de la ventana que tapa.

### 1.2 Resultado

```json
{
  "version": 2,
  "ok": true,
  "error": "",
  "window": {
    "title": "Calculadora",
    "process": "CalculatorApp",
    "processId": 1234,
    "hwnd": 460248,
    "rect": {"x": 100, "y": 80, "w": 640, "h": 720},
    "focused": {"i": 7, "kind": "Edit", "name": "Búsqueda", "value": ""},
    "coveredBy": {"title": "Película - PotPlayer", "process": "PotPlayerMini64"}, // solo si otra la tapa
    "requested": true              // la ventana se halló por la aplicación pedida (proceso, título o
                                   // navegador de la persona), no por estar delante: la App adopta su pid
  },
  "controls": [
    {
      "i": 0,
      "kind": "Button",              // ControlType UIA sin el prefijo
      "name": "Cinco",               // ≤ 80 caracteres, espacios colapsados
      "nameSource": "helpText",      // sólo si el control no tiene Name propio (v3, §8): helpText, labeledBy o automationId
      "id": "42.1837.4.12",          // RuntimeId UIA; vale sólo para esta vista
      "state": "",                   // tokens separados por espacio, ver §1.3
      "value": null,                 // Value/RangeValue si el control lo expone (≤ 120 chars)
      "rect": {"x": 120, "y": 500, "w": 60, "h": 48},   // píxeles físicos de pantalla
      "zone": "BL",                  // rejilla 3×3 sobre la ventana, ver §1.4
      "color": "gray",               // color dominante HSV del rectángulo, ver §1.5
      "itemType": "Carpeta de archivos" // sólo elementos de lista, cuadrícula o árbol que exponen ItemType (v2)
    }
  ],
  "controlCount": 43,                // accionables visibles antes del límite
  "clientProviders": true,           // v3 r3a M1: el worker leyó los controles Win32 clásicos con los proveedores del lado cliente
  "text": {                          // sólo con includeText
    "T":  ["Calculadora estándar"],
    "C":  ["12 × 7 =", "84"],
    "B":  []
  },
  "surface": "sha256-hex",           // hash de la captura de la ventana (postlecturas)
  "elapsedMs": {"uia": 180, "ocr": 900, "color": 40},
  "authority": "windows_uia_snapshot_ocr_zones"
}
```

Reglas:

- **Controles Win32 clásicos (v3, análisis r3a M1).** El worker registra una vez los proveedores UIA del lado cliente
  (`ClientSettings.RegisterClientSideProviderAssembly`, tras la primera llamada a UIA): un ComboBox, un árbol, una
  lista o un botón de control común llegan como tales y no como un `Pane` opaco. El ping y la vista lo dicen
  (`clientProviders`).
- **La app nombrada (v3, análisis r3a M5).** Sin proceso conocido, la ventana de la app es la del ejecutable de ese
  nombre, si no la de un ejecutable cuya descripción (FileDescription) es el nombre entero o el nombre seguido de más
  palabras, y si no la que el título nombra en su último segmento; nunca por una palabra suelta de la descripción.
  La descripción no cuenta en un proceso que otra aplicación lanzó (el primer ancestro de otro ejecutable, vivo, no
  es el shell ni BAXY y tiene ventanas de nivel superior): es un runtime que esa app lleva dentro (un navegador
  embebido, un ayudante web) y describe el runtime, no la app pedida. Entre las ventanas cuya descripción nombra la
  app, gana la que el título también nombra (revisión de seguridad 2026-10-07).
- **Espera de la etiqueta tras abrir (v3, análisis r3a M7).** Tope de 8 s mirando; además, con la interfaz ya levantada
  (el árbol de la última búsqueda por nombre, `treeSize`, con 20 elementos o más), si el árbol no creció desde la mirada
  anterior y la ventana queda quieta, «no encontrado» llega entonces. Una pantalla de carga o un árbol que crece
  conservan la espera.
- **Orden y selección.** Primero los accionables (`Button, MenuItem, ListItem, TabItem,
  Hyperlink, CheckBox, RadioButton, Edit, ComboBox, TreeItem, SplitButton, Slider,
  Document`), luego el resto hasta `limit`. Sólo elementos habilitados, con nombre y en
  pantalla; un accionable sin `Name` toma su nombre de respaldo (§8.1) y un `Edit`/`Document` sin ninguno
  sale como `(edit)`/`(document)`. Un mismo `kind|name` repetido se lista **una vez** con `"repeated": n`; el clic por
  etiqueta sobre un repetido es ambiguo y exige índice.
- **La ventana** es la de delante según `VisibleControlSurface` (raíz `GA_ROOT`, la ventana
  ajena más alta cuando la de delante es la nuestra). Título, nombre de proceso y pid vienen
  de Win32, no de UIA. Con `processId`, la ventana del proceso es la de delante si es suya y
  usable; si no, la mayor usable (visible, no oculta por DWM, con título): explorer.exe guarda un
  marco oculto mayor que la ventana de carpeta (`ChooseProcessWindow`).
- **Píxeles físicos.** Los rectángulos, la captura y los límites de DWM están en píxeles
  físicos; el clic por OCR/visión, la rueda y `WindowFromPoint` ponen el hilo en
  `PER_MONITOR_AWARE_V2` (a 125 % un punto lógico caía tres filas más abajo).
- **Sin árbol útil** (≤ 1 control: CEF/SDL/canvas), `controls` trae lo que hay y `text` se
  rellena siempre, con `authority: windows_media_ocr_lines`. Es el caso medido en Steam y
  en el diálogo de descarga.
- **`surface`** es el hash de la captura que se tomó para colores/OCR; sirve para comparar
  «antes/después» sin volver a capturar.

### 1.3 Estado

`state` es una cadena con cero o más tokens: `selected`, `expanded`, `collapsed`,
`on`, `off` (Toggle), `focused`, `checked`, `readonly`, `password`. `enabled` no se
lista: todo lo listado está habilitado. Un `Edit` con `password` nunca recibe texto del
motor.

### 1.4 Zonas

Rejilla 3×3 sobre el rectángulo de la ventana: `TL T TR / L C R / BL B BR`. Un control que
cruza zonas toma la de su centro. El texto OCR se agrupa por la zona del centro de cada
línea, en orden de lectura (arriba→abajo, izquierda→derecha).

### 1.5 Color dominante

Sobre la captura de la ventana, el rectángulo del control (recortado 10 % por lado) se
reduce a un histograma HSV; el color es el nombre de la clase con más píxeles entre
`red orange yellow green cyan blue purple pink white black gray`. Umbrales: S < 0,18 → gris/
blanco/negro por V; hue en grados con cortes 15, 40, 70, 170, 200, 270, 330. Es lo que
resuelve «el botón rojo» sin modelo (§3.3).

### 1.7 Rótulos y su tinta (`textMarks`, v3 punto 5)

Cuando la autoridad es el OCR (≤ 1 control), la vista trae además
`textMarks: [{text, zone, rect, ink, inkV, bgV}]`: cada línea OCR partida en rótulos donde el hueco
entre dos palabras supera 0,9 × el alto de la línea (Steam lee «BIBLIOTECA COMUNIDAD» como una
línea), sin repetir el rótulo que la segunda pasada vuelve a leer. `rect` en píxeles de pantalla.
`ink` es la clase de §1.5 de la **tinta**, no del fondo: el fondo es la mediana de V en un anillo
a 2 px del rótulo, tinta es |V − fondo| > 0,25, y la clase es la de la décima parte de la tinta
más alejada del fondo (los núcleos de los glifos, no su borde suavizado): un tono si la mayoría
de esos núcleos tiene color, si no blanco/gris/negro por su V mediana. `inkV` (0–255) es esa V:
dos tintas sin color se comparan por ella (Steam dibuja sus rótulos a V 0,87, justo en el corte
blanco/gris). `bgV` (0–255) es la V del fondo (la mediana del anillo): dice si un rótulo sin color
resalta más que sus vecinos o está atenuado (deshabilitado). Es `VisibleTextMarks` en el proveedor; no nombra aplicaciones.

### 1.6 Objetivos de latencia

| Lectura | Objetivo | Cómo |
|---|---|---|
| Vista sin OCR | ≤ 300 ms | UIA en un worker PowerShell persistente (una sola carga de `Add-Type`; medido en la herencia: spawn 243 ms + Add-Type 385 ms por llamada) |
| Vista con OCR | ≤ 1,5 s | captura DWM + Windows.Media.Ocr en dos pasadas (directa y oscurecida), ya existentes |
| Tokens al modelo | ≤ 1 200 | serialización compacta §4.2, no el JSON del recibo |

Se miden en `COMPUTER_USE_DISENO.md` §15 con el sondeo `cu_view_probe` (por tipo de app:
Win32, UWP, Electron, canvas).

---

## 2. El conjunto cerrado de acciones

| Acto | Operación | Argumentos | Postlectura (qué prueba el efecto) |
|---|---|---|---|
| pulsar | `input.visible.click` | `label` (obligatorio), `index?` (de la vista), `controlId?` (RuntimeId de la vista) | `selected` \| `absentOrDisabled` \| `surfaceChanged` \| `targeted` (campo designado, §2.2); con índice/id, el nombre del control debe coincidir con `label`; el recibo dice `method` |
| escribir | `input.text.type` | `text`, `window?` (la ventana de la misión, v2), `index?` (el campo de la vista, v3: lo pone la App) | v3: `setvalue` (valor releído), `em_replacesel`/`wm_char` (texto del control releído) o, si ningún mensaje lo alcanza, SendInput aceptado (`method: keyboard`) + el control enfocado no es `password`; en una misión, el campo muestra el texto (§7) |
| tecla | `input.key.press` | `key` (enum cerrado, ahora con combos `ctrl_a ctrl_c ctrl_f ctrl_k ctrl_t ctrl_w ctrl_z f5`), `target?` (`message_composer` \| `text_field`), `window?` (la ventana de la misión, v2) | v3: tecla sola en un control clásico, WM_KEYDOWN/UP encolados (`method: postmessage`); si no, SendInput aceptado en esa ventana delante (`method: keyboard`) |
| desplazar | `input.scroll` | `direction` (`down`\|`up`), `amount` (1..10) | hash de superficie cambió; si no, `scroll_surface_unchanged` |
| abrir / traer al frente | `app.open` | `appId` del catálogo instalado | proceso vivo + ventana visible + foco (reutiliza la instancia que ya corre) |
| enfocar ventana | `window.focus` | `windowId` (de `window.resolve`) | identidad + foreground |
| navegar (sesión propia) | `browser.navigate`, `browser.navigate.named` | ya existentes | ya existentes |
| esperar | *(no es operación)* | `waitForLabel` en la vista | la etiqueta aparece antes del tope (≤ 24 s, lección UI1735/UI1775) |
| terminar | `done` / `none` | `evidence` | la evidencia está en la vista (§4.4) |

Reglas:

- **Clic por identidad.** Cuando la etiqueta se repite o el control no tiene nombre útil,
  el modelo elige por `i`; el provider resuelve `i → controlId` de la **misma vista** y
  vuelve a leer el control antes de invocarlo. Si el nombre ya no coincide, `visible_control_stale`
  y se vuelve a mirar. Nunca por coordenadas.
- **Cascada por etiqueta** (sin índice): UIA → OCR → visión, como hoy; con la espera acotada
  sólo cuando la etiqueta no está en la última vista.
- **Nada se escribe en un campo de contraseña** (`input.text.type` → `typing_into_password_refused`).
- **Nada fuerza procesos ni cierra VS Code**: el repertorio no tiene `alt+f4` ni cierre de
  ventana; cerrar una pestaña es `ctrl_w`, con el navegador abierto (D16).

### 2.1 Riesgo por paso

El riesgo de cada paso es el de su primitiva en el catálogo, evaluado por `RiskPolicy`
con los argumentos delante:

| Paso | Modo normal | Por qué |
|---|---|---|
| clic, tecla, texto, scroll, abrir | directo | D3: pulsar y escribir en apps no destruye |
| clic cuyo `label` nombra un **canal de voz / llamada** (`canal de voz`, `voice channel`, `llamar`, `call`, `unirse a la llamada`, `join call`) | **confirma** | D15: alguien te oye; «voz pregunta antes y se queda» |
| clic cuyo `label` **empieza** por enviar, reenviar, invitar o responder (`send`, `forward`, `invite`, `reply`), o `enter`/`space` con `target: message_composer` | **confirma** | llega a una persona (misma regla que `message.send`) |
| clic cuyo `label` (≤ 6 palabras) lleva un verbo destructivo (no guardar, descartar, papelera, quitar, vaciar, limpiar, eliminar, desinstalar) o comprar/pagar en cualquier etiqueta | **confirma** | no se deshace (revisión de seguridad v2) |
| `delete` sin `target: text_field` | **confirma** | fuera de un campo de texto borra lo seleccionado |
| bypass | todo directo | identidad §«dos modos» |

La regla vive en `RiskPolicy.Evaluate(risk, mode, operation, arguments)`: el Kernel decide
sobre los argumentos exactos de la invocación, y la confirmación queda ligada a esa
invocación (invariante 4). El bucle se detiene en el paso, pregunta con lo observado
(«¿Entro al canal de voz Cotele?»), y sigue con el «sí».

---

### 2.2 Clic sin ratón (v3, arreglo 2 del punto 0)

El worker UIA nunca mueve el cursor. Pulsa el control por la primera vía que tenga y el recibo lo dice en
`method`, que llega al paso de la misión (journal y mente):

1. `invoke`, `select`, `toggle`, `expand`: el primer patrón, en ese orden (Invoke, SelectionItem.Select, Toggle,
   ExpandCollapse).
2. `target`: un `Edit` o `Document` con valor escribible no se pulsa; queda como destino del texto (`targeted: true`,
   `focused: true`). Mientras el texto no llegue al campo por su valor, sólo cuenta si tomó el foco del teclado, y el
   foco sólo se pide con su ventana ya al frente (`SetFocus` del cliente UIA trae al frente una ventana tapada: sería
   un robo de foco). Detrás, o sin el foco, sigue la vía siguiente (`targetStep`: `behind` o `unfocused` en el recibo
   del puntero). No cuenta como cambio de pantalla.
3. `legacy`: la acción por defecto de LegacyIAccessible. Un control que es su propia ventana la pide a su propio
   IAccessible (`AccessibleObjectFromWindow`): los proxies del cliente UIA administrado lo ven como un Pane sin patrones
   (medido con WinForms). Los demás controles van por el cliente COM de UIA, buscados por RuntimeId; en una vista web es
   un clic sintético dentro de la página. Si no hay acción, el recibo del puntero dice dónde paró (`legacyStep`).
4. `message`: en una ventana Win32 clásica (FrameworkId Win32/WinForm, con el DPI de su monitor),
   `WM_LBUTTONDOWN/UP` enviados con PostMessage a la ventana hija bajo el punto (BM_CLICK de un botón nativo también
   es `message`).
5. `pointer`: sólo sin ninguna de las anteriores. El worker no pulsa: responde `visible_click_needs_pointer` con el
   punto y el rectángulo, y el adaptador hace el clic por coordenadas si la ventana de la misión está al frente y
   contiene el punto (si no, `input_window_not_in_front`, nada pulsado). La regla de pausa del arreglo 3 envuelve ese
   clic.

**Superficie de render de Chromium (`render`, fable/cu-v3-clic-chromium).** WebView2, CEF y Electron dibujan su
contenido en una ventana hija de clase `Chrome_RenderWidgetHostHWND`: el tipo de superficie se reconoce por esa clase,
nunca por el nombre de la app. Medido en vivo con un cliente de mensajería WebView2 detrás de la ventana de la persona:
`WM_MOUSEMOVE/LBUTTONDOWN/LBUTTONUP` enviados con PostMessage a esa ventana, en coordenadas cliente, dieron el foco a su
buscador y seleccionaron una pestaña sin mover el frente ni el cursor; `SelectionItem.Select` sobre la misma pestaña trajo
la ventana al frente, y el buscador no tenía patrón ni acción por defecto (su única vía era el puntero). Por eso, cuando
el elemento es de un proceso con una superficie de render en la ventana del clic (o en una ventana de contenido de su
familia, ver abajo), `render` va **antes** que `SelectionItem.Select` (lo medido); Invoke, Toggle y ExpandCollapse
siguen solos, como antes (llegan al elemento exacto y ninguno se midió tomando el frente); sin patrón, `render` va tras
la acción por defecto, y un campo, tras `target`. Un campo sigue la regla de `target`: al frente, `SetFocus`; detrás,
la pulsación enviada y el foco releído hasta 400 ms (`method: target`, `via: render`); sin foco, la vía siguiente
(`renderStep: unfocused`); con el foco ya puesto antes, es ya el destino y no se pulsa (`via: prefocused`: su foco no
probaría la pulsación y el clic dejaría el cursor de texto en medio de lo escrito). Un elemento de otro proceso (el
botón de título de un marco que se superpone al rectángulo de su contenido) nunca se pulsa a través del contenido.

**Nunca a ciegas (revisión de la rama).** Antes de enviar nada se pregunta a la propia página qué tiene en el punto:
`accHitTest` del objeto accesible de la superficie, dos veces con 80 ms entre ellas (la primera arranca la prueba de
impacto de la página y responde por cajas; la segunda trae su resultado, con sus capas: cabecera fija, banner, modal),
subiendo como mucho 10 nodos. Con elemento, la respuesta debe ser el elemento o algo dentro de él (una caja igual a la
suya con su nombre, sin pasar antes por nada que se salga de su rectángulo); una ventana emergente propia (la lista de
un `<select>`, un autorrelleno, un menú) es otra ventana y la página de debajo responde otra cosa, así que nada se envía
(`renderStep: other`) y queda el patrón. Sin respuesta, `nohit`; con DPI distinto, `dpi`. Medido en vivo, de sólo
lectura y detrás de la ventana de la persona: la primera llamada dio el documento de un cliente WebView2 y la segunda,
80 ms después, su botón «Chats»; la página de un navegador dio su enlace igual; una cadena de 19 nodos tardó 430 ms en
un cliente Electron (de ahí el tope). Medido después con el worker de la rama sobre el mismo cliente detrás: «No leídos»
y «Todos» se pulsaron por `render` (postread `selected` de no seleccionada a seleccionada) y el buscador, que ya tenía
el foco, quedó `prefocused`; ni el frente ni el cursor se movieron. La prueba de `render` es la de cualquier pulsación:
su postread (seleccionado, conmutado, desaparecido) o la superficie que cambia.

En `at` (OCR o visión), si nada del árbol en el punto tiene vía y el punto cae en una superficie de render, la pulsación
se envía ahí sólo si lo que la página tiene en el punto, en el momento de pulsar, nombra la etiqueta leída (el nodo
tocado o uno de sus tres antecesores, nunca el documento): una lista que se reordenó, el botón de título de un marco
encima del contenido o una capa nueva no la nombran (medido: en el punto de «Chats», `at` con «Grupos» dio
`renderStep: other` sin enviar nada, y con «Chats» se envió). Ahí va a cualquier proceso de la familia, porque esa
comprobación es la que impide pulsar a través del contenido algo que no es lo leído; un lugar recordado sin nombre
(§8.2) nunca va por aquí. Prueba: la superficie que cambia, con la referencia tomada justo antes de la pulsación (no
antes del OCR); sin superficie o sin la etiqueta, el puntero como antes (`renderStep` en el recibo). Queda lo que
cualquier pulsación sin ratón en un punto tiene: algo que la ventana redibuje sola en los 1,5 s del postread cuenta
como cambio. El adaptador manda en `hosts` las ventanas de contenido de la familia del proceso
(`FamilyContentWindows`: ventanas de procesos descendientes, no ventanas propias, que cubren la de la app), estén encima
o debajo de ella: medido, al activarse por una apertura el marco WinUI quedó encima de su contenido en el orden Z, la vista
se quedó en el marco (8 elementos, ningún campo) y cada clic acababa en el puntero. La superficie de la vista no cambia
de regla. Medido también: una pulsación enviada a una ventana Slate (`UnrealWindow`, sin árbol) no hace nada; ahí el
puntero sigue siendo la vía.

El clic por identidad ya no trae la ventana al frente: los patrones llegan a una ventana tapada. Si la identidad quedó
vieja, la cascada por etiqueta sigue atada a la ventana de esa vista (UIA la alcanza detrás; OCR y visión sólo leen y
pulsan mientras está al frente), nunca a la ventana que la persona tenga al frente.

OCR y visión, antes del puntero, piden al worker el comando `at` con los alias de la etiqueta: sólo es candidato un
control con patrón (o campo que toma texto) cuyo nombre, o el texto de dentro, nombra la etiqueta, sin pasar de un
cuarto de la ventana, del más interior al más exterior. Con la ventana visible en el punto, la cadena de
`AutomationElement.FromPoint` (lo que se ve: una capa o un modal tapan lo de debajo); con la ventana tapada ahí, los
controles cuyo `BoundingRectangle` contiene el punto. Sólo la respuesta explícita del worker de que nada ahí tiene
vía (`visible_point_no_pattern`) deja el puntero, y el puntero pasa por la misma guarda que el de UIA (ventana al
frente, punto dentro, recaptura justo antes; si no, `input_window_not_in_front`). Un silencio, un timeout o un error
después de empezar a pulsar es `visible_point_press_unconfirmed` con `effectMayHaveOccurred`: nunca se pulsa otra vez.
Pruebas: `ComputerUseClickMethodTests`.

**Patrones sin tecla ni robo (goal v3 punto 0, r4a M1).** Antes de un método de patrón, UIAutomationCore pide a
Windows el permiso de primer plano y se lo cede a la aplicación: con la persona tecleando lo gana registrando la
tecla VK 0xB9 como hotkey del hilo, inyectándola sin marca (cae en la ventana de la persona) y esperando su
`WM_HOTKEY` hasta 2 s. El worker, al cargar el cliente, desvía en la tabla de importaciones de UIAutomationCore
`SendInput` y `RegisterHotKey`/`UnregisterHotKey` (se siguen). Solo se descartan las teclas cuyo VK es un hotkey
que registró ese mismo hilo (lo medido): nada llega a la pantalla ni gana el permiso, y la espera se contesta con el
`WM_HOTKEY` que el cliente esperaba. Cualquier otra entrada (ratón, otra tecla, un lote mezclado) se rechaza entera:
no se envía y la llamada devuelve 0, así un patrón que necesitara entrada simulada no da por hecho lo que no pasó
(`BaxyUiaQuietInput`; el ping dice `quietInput`, `uiaInputDropped`, `uiaInputRefused`, `uiaWaitAnswered`). Sin nadie
tecleando, el cliente cede el permiso sin tecla. Por eso los comandos que actúan (`click`, `at`, `field`, `reveal`,
`scroll`) corren bajo `BaxyFrontKeeper`, una red que devuelve el frente. Mientras actúan, y
300 ms después si un patrón actuó de verdad (`invoke`, `select`, `toggle`, `legacy`, `message`, `setvalue`, un
desplazamiento o un revelado), vigila a la familia del objetivo: su ventana, su proceso, los de sus ventanas hijas y
una ventana que posee. Si toma el frente de la persona, se le devuelve con `SetForegroundWindow`. Si Windows lo
niega, el hilo de la red gana el derecho igual que el cliente: tiene registrado como hotkey propio una VK sin teclado
(0x97, o la primera libre de su lista) con las 16 combinaciones de modificadores, la pulsa una vez con la marca de BAXY
y, al llegar su `WM_HOTKEY`, devuelve el frente. El sistema se queda la pulsación y su subida: medido en vivo, ni la
ventana de la persona ni la del objetivo reciben mensaje de teclado (`frontBids`, `frontBidsAnswered` en el ping).
Solo si el frente releído es de verdad el de la persona, el objetivo pasa justo debajo sin activarse. Si el retorno
falla, el orden Z no se toca: la ventana que tiene el teclado sigue a la vista.

La red no pelea un cambio que hace la persona: un clic o una tecla que mueve el frente (Tab, Enter, Esc, Alt, Win,
una tecla de función), vistos por Raw Input pasivo sin la marca de BAXY; sin Raw Input, cualquier entrada desde que
empezó. Expandir un menú o un desplegable suelta la vigilancia, porque se cierran al perder la activación. Tras una
respuesta sin efecto no hay cola: el puntero, la rueda o el teclado del adaptador toman el frente a propósito dentro
del lease. Además, el lease escribe en un bloque compartido de la sesión (`LeaseFrontSignal`, `Local\BaxyLeaseFront`)
qué ventana trae al frente y cuándo, y la red no pelea ese frente si se dijo hace menos de 2 s. Cada comando y su `postread` llevan el parte de su vigilancia (`frontChanged`, `frontRestored`,
`frontReturnFailed`, `frontReturnMs`), y los recibos de clic, campo, revelar y ScrollPattern lo copian para el medidor
de molestia de la misión. Un frente devuelto sigue siendo un cambio, y un retorno fallido es un cambio no restaurado.
El recibo del clic por punto (`at`) todavía no lo copia. Medido en vivo: sobre 1b9b736e7, con la persona quieta, una
excursión de 2399 ms y `frontReturnFailed`=2. Con el hotkey de la red (4 corridas seguidas de los dos regímenes),
tecleando: 0 excursiones; quieta: excursiones de 5 a 12 ms (muestreo cada 5 ms) y `frontReturnFailed`=0. En los dos
regímenes, 0 teclas ajenas en la ventana de la persona y 0 en la del objetivo, y los cuatro efectos hechos. Cambios de
frente que llegan después de la vigilancia: solo se cuentan (`frontLate`, `frontLateMs`).
Pruebas: `UiaQuietInputTests` y `UiaFrontReportTests`; en vivo, `UiaSinFrenteLiveCheck` (tecleando y quieta).

**Devolución desde el proceso de BAXY (cu-v3-foco-segunda).** Toda devolución del frente que hace el propio proceso
—la de una apertura (`app.open`, `file.open` con aplicación, su guard de 3 s y las miradas mientras arranca), la del
lease tras una ráfaga y la del teclado— pasa por `ForegroundRight`: `SetForegroundWindow` adjunto al hilo del frente,
releído; si no quedó, la misma puja que la red (hotkey propio del hilo sobre la primera VK libre de la misma lista, 16
combinaciones, una pulsación marcada, espera de `WM_HOTKEY` ≤ 200 ms) y otra vez; hasta 3 intentos con 60 ms entre
ellos. Medido en vivo con tres apps empaquetadas seguidas en un proceso: antes, la primera devolución valía (el derecho
con que nace un proceso) y las siguientes Windows las negaba (`SetForegroundWindow` falso con la entrada adjunta,
error 0); Bloc de notas además volvía a tomar el frente 30 ms después desde otro proceso suyo, que el guard no
reconocía. Después: las tres devueltas (la primera sin puja, Paint con una, Calculadora con una y un segundo intento),
y Fotos seguida de Bloc de notas por `file.open`, también. El recibo de la apertura dice `windowsActivation` y
`frontRestored` (la devolución releída, nunca supuesta); el guard devuelve cada vez que la app toma el frente de
nuevo (la ventana de su proceso, de uno que lanzó o de otro proceso del mismo programa) y se detiene ante una
devolución negada; la vista siguiente cuenta `windowsActivationsReturned` y `windowsActivationsNotReturned`.
Pruebas: `ForegroundRightTests`; en vivo, `AppOpenFrontLiveDesktopCheck` (BAXY_CU_FRENTE_LIVE=1, con turno).

## 3. Grounding: de lo que dijo la persona a un control

Orden fijo; el primero que resuelve gana; con dos candidatos se pregunta, nunca se adivina.

1. **Texto.** Nombre UIA (o su respaldo, §8.1), `aria-label` (es el nombre UIA en Electron/Chromium) o línea OCR,
   tolerante a errata: comparación plegada (sin acentos, minúsculas) y distancia de edición
   ≤ 1 por cada 5 caracteres; alias bilingües del catálogo (`biblioteca`/`library`,
   `configuración`/`settings`, dígitos ↔ nombres).
2. **Plantilla local (OpenCV).** Para «el icono de X» sin texto: el icono se obtiene del
   sistema (`IShellItemImageFactory` para accesos directos y apps instaladas; carátulas de
   Steam en `librarycache`) y se busca en la captura por `matchTemplate` (TM_CCOEFF_NORMED
   ≥ 0,80, escala 0,75–1,25). Corre en CPU dentro del runtime Python de la mente
   (`opencv-python-headless`); el provider recibe un rect y lo trata como un control OCR.
3. **Color.** «el botón rojo/verde/azul»: el control cuyo `color` (§1.5) coincide y cuyo
   `kind` es accionable. Uno → clic; varios → pregunta enumerando nombres.
4. **Encoder imagen-texto pequeño** (MobileCLIP2-S0 o SigLIP 2 ≤ 150 M, CPU) y
   **Florence-2-base** (0,23 B, MIT, CPU) para «clickea en <cosa>» sin texto y «qué imagen
   veo»: **no se construyen** en esta fase. Se activan sólo si el banco de la encuesta lo
   exige, con números (RAM, latencia, filas que desbloquea) presentados al dueño. Un VLM
   grande queda fuera salvo decisión del dueño.

---

## 4. La misión (`mission.computer.use`)

Operación nueva del catálogo, riesgo `low_reversible`, contrato
`mission.computer.use.shell.loop.v1`, `requiresObservedEffect: false`. El core no la ejecuta
(`computer_use_requires_shell`): la corre el shell, y cada paso que da es una operación
journalizada por el Kernel. Así la misión aparece en el plan como un paso más
(`CHAIN1931`: un efecto por paso, proyección de evidencia del prefijo completado,
grounding dependiente).

### 4.1 Argumentos

```json
{
  "goal": "ir a la biblioteca",          // ≤ 512 bytes, lo pedido, normalizado
  "application": "Steam",                // opcional; nombre del catálogo instalado
  "successCheck": "control:Biblioteca:selected|text:Biblioteca",   // opcional, §4.3
  "budgetSteps": 12                      // opcional, 1..12
}
```

Presupuesto de tiempo fijo: 90 s de misión; cada vista ≤ 30 s, cada primitiva ≤ 45 s.

### 4.2 Una vuelta del bucle

1. **Mirar.** `input.visible.controls {includeText: true}` (con `waitForLabel` cuando el
   paso anterior esperaba una etiqueta). La ventana es la del proceso que la misión ya
   conoce (`processId`, tomado del `app.open` que hizo o de la primera vista con
   `window.requested`) o, hasta entonces, la de `application` (§1.1); sin aplicación,
   la del primer plano. Si `successCheck` ya se cumple → fin; si la vista trae
   `window.coveredBy`, la misión para (`computer_use_window_covered`).
2. **Decidir.** `computer.use.step` a la mente (§4.4). Primero lo que el objetivo dicta sin
   modelo (`cu_rules.deterministic_step`): la aplicación pedida no está delante →
   `app.open`; «apretar <tecla>» → esa tecla; «calcular <expr>» → escribir la expresión y
   Enter; «escribir <texto>» → escribirlo; «ir a / hacer clic en <X>» → clic en el control
   que se llama X si está en la vista; «activar/desactivar <X>» → clic en ese control si su
   estado no es ya el pedido; «ir a la pestaña X» → clic en la `TabItem` cuyo título
   contiene X (el tipo de control nombrado en el objetivo acota la búsqueda). «seleccionar / ir a / hacer clic en <X>»
   sin control listado ni línea escrita que lo nombre, cuando la vista lista sólo parte del árbol (`controlCount` mayor
   que los listados): un clic por la etiqueta sola con el nombre del objetivo (la palabra de la persona, después la del
   otro idioma), que el provider resuelve en todo el árbol; cada nombre una vez por sub-objetivo, nunca con un tipo de
   control nombrado, ni para activar/desactivar, ni con un nombre que borra o abre otra ventana (medido en Paint: los
   colores quedan más allá de los 60 controles listados). Un paso que acaba de fallar nunca se repite: lo que sigue lo decide el
   modelo, con JSON estricto y temperatura 0 (medido en la Calculadora: el modelo pulsando
   dígito a dígito agotó los 90 s; con el paso dictado la misión son dos pasos).
3. **Actuar.** La primitiva va al Kernel como operación con sus argumentos; el Kernel
   autoriza (§2.1), el provider ejecuta y verifica.
4. **Registrar.** El paso queda en la misión con `{operation, args, ok, error, changed,
   window}` y en el journal; el hito se narra a la persona («Paso 3: clic en Biblioteca»)
   cada ≤ 3 s.
5. **Parar** cuando: `successCheck` se cumple (o el modelo dice `done` con evidencia
   presente en la vista); `budgetSteps` o 90 s agotados (`computer_use_budget_exhausted`);
   dos vistas seguidas iguales tras actuar (`computer_use_surface_unchanged`); el modelo
   dice `none` (`computer_use_no_step_visible`); otra ventana tapa la aplicación y no cede
   (`computer_use_window_covered`); una primitiva pide confirmación (la misión queda
   pendiente y se reanuda con el «sí»).

**Reintento acotado.** Una primitiva que falla sin efecto (`visible_button_not_found`,
`scroll_surface_unchanged`) se registra y el modelo vuelve a decidir con ese fallo en el
historial; el mismo acto sobre el mismo control se rechaza a la segunda
(`computer_use_repeated_step`) y se pide otro. Una vista que no cambió como el paso
esperaba (por ejemplo, tras `app.open` sigue otra ventana) es una **replanificación**:
la mente recibe `history` y decide de nuevo; no hay plan previo que reparar.

### 4.3 `successCheck`: gramática

Cadena determinista evaluada por el shell sobre la última vista y sobre recibos
independientes; nunca por el modelo.

```
check   := term ( "|" term )*          # OR de términos; un término con "&" es AND
term    := atom ( "&" atom )*
atom    := "text:" needle              # needle plegada dentro de algún control o línea OCR
         | "control:" name [ ":" state ]   # control con ese nombre (plegado) y, si se da, ese estado (selected|current|on|off|expanded|focused)
                                       # current: selected y no es un elemento de contenido (ListItem/DataItem fuera de la
                                       # columna izquierda L/TL/BL, o en ella pero con un mosaico del mismo tamaño ±25 % en su
                                       # fila); es el estado de «ir a X». «control:=X»: el nombre entero. Un nombre nunca lleva
                                       # «&» ni «|» (se comprueba por la pieza de antes; la del usuario, por la más larga ≥ 4).
         | "header:" name               # el último clic verificado nombra X y un Text arriba (T/TL/TR) que lo nombra apareció
                                       # tras ese clic (la cabecera de un modo: «Modo de calculadora Científica»)
         | "focus:search"               # «ir a buscar/search/búsqueda»: el foco está en un Edit/ComboBox (no readonly, ni
                                       # contraseña, ni barra de direcciones) que no lo tenía en la primera mirada de la app,
                                       # el último paso verificado fue un clic en un control de búsqueda (o en ese campo) o una
                                       # tecla de buscar (ctrl_f, ctrl_k, ctrl_e, f3) y no se escribió nada en el sub-objetivo
         | "mark:" name                 # sin árbol (≤ 1 control; tapada vale: su dibujo propio) y es la ventana de la misión (requested, o la
                                       # de delante si la misión no nombra app; con la app nombrada cerrada el adaptador
                                       # lee la de delante y eso nunca pasa): el rótulo de textMarks (§1.7) que es X entero
                                       # tiene una tinta distinta de la de ≥ 2 vecinos de su franja (centro a ≤ ½ alto),
                                       # que comparten una (mismo tono, o sin color con |ΔinkV| ≤ 40; distinta: otro tono,
                                       # color contra sin color, o |ΔinkV| ≥ 64); si X no tiene color, además resalta del fondo más
                                       # que cada vecino (|inkV−bgV| de X ≥ el del vecino + 64): un rótulo atenuado no pasa. No juzga el rótulo que algún clic del
                                       # sub-objetivo pudo pulsar (verificado, o fallido con effectUncertain: el puntero
                                       # o la pulsación pueden realzarlo). Es la llegada «ya estaba ahí»
                                       # de la primera mirada (v3 punto 5); va al final de los checks de «ir a» y de modo
         | "title:" needle              # título de la ventana de delante
         | "born:" kind                 # «abrir una pestaña/ventana nueva de X» (ronda 20 P8): un TabItem seleccionado con X
                                       # en el nombre y más TabItems con X que en la primera mirada del sub-objetivo
                                       # (una ya abierta no cuenta hasta que nace otra), o una ventana nacida en la misión
                                       # (born) titulada con X cuando el título de la primera mirada no lo tenía.
                                       # Revisión 3: nunca una nacida sobre una búsqueda de X (eco de la consulta,
                                       # título que repitió lo tecleado o página de resultados web, v3-59 r7)
         | "process:" name              # proceso de la ventana de delante
         | "count:" kind op N           # número de controles de ese kind (op: <= < == >= >)
         | "value:" name "=" needle     # value de un control (por ejemplo la pantalla de una calculadora)
         | "file:" path                 # recibo independiente: existe el fichero y se escribió desde el inicio del
                                       # sub-objetivo (subgoalStartedUtc, 2 s de holgura); un fichero viejo no cumple
         | "manifest:" appid            # recibo independiente: appmanifest_<appid>.acf existe
         | "audio:" process             # recibo independiente: hay sesión de audio de ese proceso
```

Ejemplos de las seis misiones de CU1959:

| Pedido | `successCheck` |
|---|---|
| ve a Cotele en Discord | `title:Cotele\|control:Cotele:selected\|text:Voz conectada` |
| ve a la pestaña de YouTube | `control:youtube:selected\|title:youtube` (aplicación «navegador») |
| abre Steam y ve a la biblioteca | `process:steam&(control:Biblioteca:selected\|text:Biblioteca)` — el paréntesis no existe: se escribe `process:steam&control:Biblioteca:selected\|process:steam&text:Biblioteca` |
| en Discord apretá enter | `process:Discord` + el paso `key:enter` verificado (`stepDone:key:enter`) |
| abrí Configuración y activá el modo avión | `control:Modo avión:on` |
| en la calculadora calculá 12×7 | `value:Pantalla=84`? No: `84` no se afirma sin verificar. `text:12 × 7 =` y el modelo dice `done` citando la pantalla; el final cita lo observado |

`stepDone:<op>[:<arg>]` es un atom más: se cumple cuando un paso verificado con esa
operación (y ese `key`/`label`) está en la misión. `stepDone:input.visible.click:=X`: el clic nombra X entero, no
dentro de otra palabra (medido en Paint: «red» dentro de «Rectángulo redondeado» dio por elegido el rojo); un `=` solo
sigue siendo la tecla igual.

**Eco de la consulta** (`QueryEchoNames`). Mientras lo último tecleado sea el nombre del lugar en una
búsqueda o una barra de direcciones y nada lo haya enviado, o una búsqueda lo envió y su cuadro aún lo
contiene sin que un clic haya ido de los resultados al lugar por su nombre, `title:`, `page:` y
`control:X:selected|current` no se cumplen: la ventana repite la consulta («imagenes - Resultados de la
búsqueda en ETC», su pestaña elegida igual). Un clic que sólo seleccionó (recibo `selected` o un
`ListItem`/`DataItem`/`TreeItem`) no sale de los resultados. Una dirección, un «ir a» o un selector rápido
enviados llevan al lugar; un término que pide el acto de buscar (un `stepDone` junto a `title:`/`text:`,
`SearchResultsProve`) se queda con sus resultados. Lo mismo vale para la evidencia que cita el modelo:
lo que el sub-objetivo tecleó nunca es evidencia de haber llegado (`CitationEchoesQuery`).

### 4.4 Protocolo mente ↔ shell: `computer.use.step`

Petición del shell (JSONL, mismo canal que `plan.ground`):

```json
{
  "type": "computer.use.step",
  "objective": "abre Steam y ve a la biblioteca",   // lo que dijo la persona
  "goal": "ir a la biblioteca",
  "application": "Steam",
  "successCheck": "…",
  "view": { …§1.2, sin surface/elapsedMs/id; con rect e itemType, que la mente usa y el prompt del modelo no imprime;
            newText: lo que la última mirada vio nuevo; newTextAfterClick: lo que apareció en la mirada que siguió al
            último clic verificado del sub-objetivo (≤ 12 líneas; vacío sin clic), con sólo pasos fallidos después;
            controlCount: cuántos controles tiene el árbol además de los ≤ 60 listados… },
  "history": [ {"step": 1, "operation": "app.open", "applicationName": "Steam", "ok": true},
               {"step": 2, "operation": "input.visible.click", "label": "Tienda", "ok": true, "changed": true} ],
  "budgetLeft": 10
}
```

La mente construye el prompt compacto (una línea por control: `i·kind·name·state·zone`,
luego el texto por zonas, ≤ 1 200 tokens) y pide al modelo **un** paso con `response_format`
de esquema JSON (gramática, temperatura 0):

```json
{
  "act": "click|type|key|scroll|open|done|none",
  "i": 12,                 // índice de la vista (click); -1 cuando no aplica
  "label": "Biblioteca",   // nombre tal como está en la vista (click)
  "text": "…",             // type
  "key": "enter",          // key (enum del catálogo)
  "direction": "down",     // scroll
  "application": "Steam",  // open
  "evidence": "…",         // done: texto presente en la vista que prueba el objetivo
  "why": "…"               // una frase
}
```

Comprobaciones deterministas antes de devolver al shell (sin modelo):

- `click`: `label` debe coincidir (plegado, errata ≤ 1/5) con `controls[i].name` o con una
  línea OCR; si no, se busca por texto en la vista y se corrige `i`; si sigue sin estar →
  `none` con `why`.
- `done`: `evidence` debe estar (plegada) en la vista; si no, se rechaza y se pide otro paso
  (un reintento) — «nada se afirma sin verificar».
- `type` con el foco en `password` → `none`.
- Un paso igual al último fallido → `none`.

Respuesta:

```json
{"type": "computer.use.step.result", "id": "…", "operation": "input.visible.click",
 "arguments": {"label": "Biblioteca", "index": 12}, "reason": "…"}
```

`operation` es la primitiva del catálogo (`app.open`, `input.visible.click`,
`input.text.type`, `input.key.press`, `input.scroll`) o `done` / `none`.

Con etiquetas traducidas (§4.4.1) la petición puede llevar `"labelTranslations": {"date and time":
{"names": ["Fecha y hora"]}}` y la respuesta `"alias": {"from": "date and time", "to": "Fecha y hora"}`
y `"translation": {"label": "date and time", "names": […], "source": "model|cache"}`.

#### 4.4.1 Etiquetas traducidas (v3, punto 6)

Un lugar dicho en un idioma sobre una ventana en el otro («go to date and time» en una
Configuración en español) cuyos nombres no están en la tabla de `semantic/missions.py`
(`label_alternatives`).

- **Mente** (`cu_model_calls.translate_label`, `LabelTranslator`): sólo cuando ningún nombre del
  objetivo ni de la tabla encuentra control (ni lo lleva un control ni una línea del OCR), y sólo
  para etiquetas traducibles (`label_translatable`: la tabla no la conoce, ≤ 5 palabras, ≤ 40
  letras, no es un nombre de acto como «archivo», «nuevo», «abrir», «vista», «eliminar»,
  «instalar», ni un acto de cuenta como «following»). Una llamada corta al modelo local: gramática
  `{"es":[≤2],"en":[≤2]}`, temperatura 0, `max_tokens` 48, **sólo el nombre de la etiqueta** (nunca
  el pedido ni la pantalla; nada va a la web). Una traducción vale sólo si la vista muestra un
  control cuyo nombre entero es ella (sin contención ni errata; en una ventana sin árbol, una línea
  del OCR que es exactamente ella), y nunca: un nombre que la tabla conoce como otro lugar
  («Diseño» es «design», nunca «layout»); yendo a un lugar, un interruptor; un acto de cuenta que
  el objetivo no pide, una eliminación, algo que abre otra pestaña o ventana, o una herramienta al
  elegir color (las guardas de los clics del modelo); un DataItem, un elemento de contenido, ni
  las listas y árboles de una ventana que escribe a personas (un campo o línea de mensaje o chat).
  Un pedido que escribe o envía (`writes_or_sends`) no traduce nada: sus lugares son contenido de
  la persona. El clic lleva `alias {from, to}`; el paso informa `translation` siempre que se buscó una.
- **Shell** (`ComputerUseMission.NoteTranslation`): acepta el alias sólo si la vista contiene
  `to`, lo guarda en `state.aliases` (`{from plegado: [to…]}`) y `Evaluate`/`EvaluateReceipts`
  prueban cada término también con `from` sustituido por `to` en los átomos que lo nombran entero
  (`control:`, `stepDone:input.visible.click:`, `text:`, `title:`, `page:`, `header:`, `mark:`),
  átomo por átomo: el check fijado (≤ 512 bytes) no cambia y un `&` en la traducción no lo rompe.
  En `control:` y `stepDone:input.visible.click:` el nombre sustituido va con `==` (igualdad
  plegada del nombre entero: `control:==Datos` no se cumple con «Uso de datos»). Un clic de alias
  que falla deja de extender el check. Las peticiones siguientes de la misión llevan los nombres
  que ya consultó (una consulta al modelo por etiqueta y misión).
- **Aprendizaje**: nada se escribe en la caché al decidir. Al cerrar el sub-objetivo, si llegó por
  un término aliasado, `Seen()` (y el nombre entra en `onScreen`); si el clic de alias falló o no
  llegó, o si la mente consultó una traducción y ningún vistazo del sub-objetivo mostró ninguno de
  sus nombres, un rechazo: como mucho uno por etiqueta y misión. Al entrar en un sub-objetivo los
  nombres `onScreen` de su etiqueta se arman como alias, así que un clic posterior en el nombre
  mostrado sigue probando el lugar dicho; un alias armado nunca cuenta rechazos.
- **Caché** (`ComputerUseLabelTranslations`): `<data root>/computer-use/label-translations.v1.json`,
  `{"version":1,"labels":{"date and time":{"names":["Fecha y hora","Date & time"],
  "onScreen":["Fecha y hora"],"seenOnScreen":3,"rejected":0,"learnedUtc":…}}}`. Cada `computer.use.step` lleva sólo la entrada de la etiqueta
  más larga que el objetivo nombra con palabras enteras, y sólo sus `names`; con entrada no se
  llama al modelo. Tres rechazos seguidos la olvidan; verla en pantalla los pone a cero. La
  tabla manda: la mente nunca traduce ni lee la caché de una etiqueta que la tabla conoce.

#### 4.4.2 Parecido de significado (v3, r5a/decision.md P1–P5)

- **Encoder**: el E5-small que la mente ya carga (`router.RequestBudgetEncoder`); cada
  `computer.use.step` tiene 0,75 s de encoder, contados sólo mientras codifica (la traducción de la
  etiqueta por el modelo no lo gasta: `SemanticMatcher` renueva el plazo a lo que queda). Las filas se cachean por nombre
  durante la vida de la mente (`semantic/cu_semejanza.EmbeddingCache`). Si el encoder falla, está
  ocupado o se pasa del presupuesto, el paso es el literal de siempre. Un pedido que escribe o
  envía (`writes_or_sends`) no empareja nada.
- **Clic sin modelo** (P1, `cu_meaning._semantic_step`): sólo cuando ningún nombre del objetivo,
  de la tabla ni de la traducción está en pantalla. El nombre más parecido a la etiqueta (o a sus
  traducciones) con coseno ≥ 0,86 y margen ≥ 0,03 sobre el mejor nombre distinto (una extensión
  «Nombre, …» no cuenta; un nombre que no se puede pulsar sí: «Deshacer Insertar tabla» cerca de
  «Tabla» es duda). Filtros: un solo control con ese nombre; ListItem, TabItem, TreeItem,
  MenuItem, Hyperlink o Button; nunca interruptor salvo «activar/desactivar»; nunca quitar, cuenta,
  otra pestaña o ventana, marco («Cerrar …», «Minimizar»), deshacer/rehacer/repetir, DataItem,
  un control listado sin rectángulo (el menú de sistema) ni una ventana que escribe a personas. Lleva `alias {from, to}` como una traducción (§4.4.1). Un
  objetivo libre de ≤ 6 palabras se empareja una vez, antes de cualquier clic del sub-objetivo.
  Calibrado en `tests/test_cu_v3_semejanza.py` (precisión ≥ 0,98).
- **Lo plegado** (P5): sin clic, hasta dos controles `collapsed` (ComboBox, Button, MenuItem,
  TreeItem; nunca SplitButton) con parecido ≥ 0,84, el más parecido primero, se abren antes de
  buscar; sin puntajes (encoder caído o agotado) no se abre nada. Nunca uno sin rectángulo ni uno en
  la banda de los botones del marco (cuenta, barra de acceso rápido); con parecidos para el modelo,
  sólo el primero de ellos.
- **Decide el modelo** (P2): si hay parecidos ≥ 0,84 y la búsqueda no empezó, el paso es del
  modelo, con la línea «Parecidos al objetivo: [i] nombre · …» y esos controles primero en la vista
  recortada; el reintento tras un rechazo nombra el primero y no ofrece «none». Si el modelo
  contesta «none», el paso literal (la búsqueda de la ventana) es el respaldo.
- **Llegada por efecto** (P3): en un sub-objetivo sin check, o en una pestaña, un clic verificado
  que cambió la ventana sobre el control que el objetivo nombra (entero o por significado con el
  umbral del clic) y una línea nueva en pantalla dan `done` citando esa línea. En una pestaña, sólo
  si ninguna pestaña de la vista está marcada `selected`. Nunca si el clic abrió un menú, si el
  control quedó `expanded` o si hay un `Menu` abierto; la línea citada nunca lleva el nombre pulsado
  (su tooltip).
- **Búsqueda** (P4): el campo se elige primero por su nombre de búsqueda («Buscar:», Edit o
  Document) y después por tipo. Un Document es búsqueda sólo si su nombre entero es una etiqueta de
  búsqueda y, con rectángulos, es un campo pequeño de una línea; nunca se selecciona todo en un
  Document con texto, y uno con texto y el teclado cuenta como otro campo; tras `ctrl_k`/`ctrl_f` sólo se escribe en un campo que se llama
  búsqueda o que apareció con un aviso de búsqueda; un campo vacío distinto se cierra con Escape.
- **Auditoría**: con `BAXY_MIND_MODEL_CALL_AUDIT_PATH`, la fila de cada paso de computer use lleva
  `messages` (el prompt completo) y `raw_reply`; las demás llamadas siguen sin contenido.

### 4.5 Resultado observado de la misión

Lo que ve el compositor (proyección `seen`), y lo que va al journal como resultado del paso
de plan:

```json
{
  "goal": "ir a la biblioteca",
  "application": "Steam",
  "reached": true,
  "successCheck": "…",
  "satisfiedBy": "control:Biblioteca:selected",
  "stepCount": 2,
  "steps": [
    {"step": 1, "operation": "app.open", "applicationName": "Steam", "ok": true, "alreadyRunning": true},
    {"step": 2, "operation": "input.visible.click", "label": "Biblioteca", "ok": true, "changed": true, "cascadeStage": "ocr"}
  ],
  "window": {"title": "Steam", "process": "steamwebhelper"},
  "joined": false,                 // sólo cuando un paso fue un canal de voz confirmado
  "evidence": "Biblioteca",
  "screen": {"title": "Steam", "values": [{"name": "Pantalla", "value": "La pantalla muestra 84"}], "lines": ["12 × 7 =", "84"]},
  "elapsedMs": 6100,
  "modelMs": 2400,
  "authority": "shell_loop_over_uia_ocr_postread"
}
```

Cuando la misión no llega, `stoppedBy` (código) se proyecta al compositor como `stoppedBecause`,
una causa en palabras de la persona («no vi en la pantalla un control con el que seguir»),
porque «operación» es un término vetado en los finales y el modelo lo escribía solo.

`screen` es lo que la ventana mostraba al terminar (valores de sus campos y unas líneas): el
final cita un valor o una línea cuando responde al objetivo (la pantalla de la calculadora).

Vetos del compositor (mente): `joined_claimed` invertido (decir «entré al canal» sin
`seen.joined`, o negarlo con `seen.joined: true`), pasado falso («ayer», «la semana
pasada»), número no observado, imperativo eco, y `reached: false` narrado como logro.

---

## 5. Memoria de procedimientos (retirada)

Retirada en la estabilización (2026-10-11, rama `fable/estab-p3-sin-procedimientos`). Decidía la mitad de los pasos
del banco sin ganar ningún caso ni ahorrar tiempo de modelo, y desde una vista de partida distinta repetía un clic
viejo que fallaba (análisis `cu-v3/estab/procedimientos.md`; apagada en aa76ba99a). La misión ya no guarda ni
reproduce secuencias: cada paso lo decide la mente sobre la vista actual. `procedures.v1.json` ya no se lee ni se
escribe.

---

## 6. Lo que este contrato no decide

- La **lectura del pedido** (qué frases van a `mission.computer.use`) es de la mente
  (`computer_use.mission_request`, decidido en `semantic/patterns.resolve_explicit_effects`):
  «en <app> <hacé X>», «abre <app> y <hacé X>», «<hacé X> en <app>», en cualquier persona
  (tú, vos, usted, infinitivo, inglés), y «andá a la pestaña de X» (aplicación «navegador»).
  Prioridad, por la forma del pedido y nunca por una lista de apps:
  1. ir a una pestaña → misión;
  2. si los lectores dan una operación tipada, gana ella (D21: ficheros, radios, música,
     búsquedas, Windows lo verifica mejor que la pantalla) salvo que sea sólo primitivas que
     la misión hace por sí misma (`app.open`, `input.visible.*`, `input.text.type`,
     `input.key.press`, `window.focus`); una lectura tipada como `client.channel.locate`
     (canal hallado y pregunta antes de unirse) conserva su ruta;
  3. sin lectura tipada, la misión gana sólo si la cláusula es un acto con comprobación de
     éxito propia (ir a, tecla, calcular, activar/desactivar, escribir, clic) y no es ella
     misma un pedido del catálogo («activá el micrófono»); un verbo suelto («en Spotify baja
     el volumen») queda para el decisor, que también tiene la misión entre sus herramientas.
- **Cerrar todas las pestañas** no es una misión: es `browser.control {action: close_all}`,
  que `RiskPolicy` confirma por su argumento y que cierra la pestaña activa una a una hasta
  dejar una, releyendo el marco tras cada cierre (`documentacion/NAVEGADOR_USUARIO.md`).
- Los **modelos de visión** (§3.4) y su decisión con números.
- La **política de cierre** de lo que la misión abrió: nada se cierra al terminar (D16).

---

## 7. Versión 2 (2026-10-07): universal, encadenado y rápido

Pedido del dueño: que BAXY use el PC como una persona —cualquier app, por cómo está hecho el motor—, con
misiones encadenadas y lo más rápido posible con calidad.

**Encadenado.** `mission.computer.use` acepta `steps` (1..10 sub-objetivos `{goal, application, successCheck}`) y
`budgetSteps` hasta 30. La mente parte el pedido en cláusulas de hacer («abrí X, andá a Y y escribí Z»), arrastra la
aplicación y la cambia cuando una cláusula nombra otra. El bucle corre los sub-objetivos en orden (≤10 pasos y 30 s
cada uno, ≤30 pasos y 180 s en total), con su propia comprobación, historial y procedimiento; al cambiar de
aplicación olvida el proceso adoptado. El resultado trae `subgoals[]`; el final narra cada parte o la primera que
no se logró.

**Límites (estabilización L, dueño 2026-10-10).** Arrastrar o dibujar con el mouse es un límite declarado: no hay
acto que lo haga (`input.pointer.drag` se retiró del catálogo); `semantic/drag.py:asks_to_drag` lee el acto (nunca el
texto dictado, citado o buscado, ni una ventana movida a un lugar de la pantalla, ni el puntero) y el contrato de «sin
operación» lo dice; ni el lector de misiones ni el motor lo intentan. El clic derecho y el formato de la cinta se leen
sobre el ACTO de cada sub-objetivo (`semantic/limits.py:act_limit`, datos `computerUse.limits.kinds`) y lo marcan
(`steps[].limit`): el bucle hace los anteriores y para al llegar sin mirar ni actuar (`computer_use_limit_<límite>`).
Un lugar que necesita un dispositivo («ir a Wi-Fi») lleva `steps[].requires`: el bucle lo lee una vez con la operación
del dato (`wifi.radio.status`, `bluetooth.radio.status`) antes de mirar y para con `computer_use_limit_device` si falta.
Tres desplazamientos de rueda que movieron la lista sin llegar son `limit:long_list`. El suelo
(`cu_finals.limit_final`) dice lo que hizo antes y el límite con su causa; también la cadena que agotó pasos o tiempo.
Una misión de un objetivo marcada es un único paso con el presupuesto de un objetivo. «guarda esto» sin aplicación ni
ventana y sin ruta tipada se pregunta «¿En cuál ventana?», y la respuesta que nombra la ventana sigue el pedido.

**BUSCAR (universal, sin modelo, `cu_lookup._find_step`).** Si el destino no está en la vista: el campo o botón
de búsqueda visible (léxico bilingüe) → escribir el destino → clic en el resultado que lo nombra (nunca Enter: un
canal de voz sigue siendo un clic que `RiskPolicy` confirma); un botón de búsqueda pulsado que cambió la ventana
abrió su cuadro y se escribe aunque el árbol no informe el foco (el buscador rápido de Discord). Si no hay buscador y
el objetivo es «ir a», el botón de navegación o menú de la ventana aún no usado («Abrir navegación», «Open
Navigation», «Menú principal», «Más opciones», «Main menu», «Hamburger menu»; por su nombre entero,
`Button`/`MenuItem`/`SplitButton`, nunca un interruptor ni uno ya `expanded`; «Menú» o «More» solos no valen, y con
campo de dirección sólo uno dentro de la página) y el destino se busca entre lo que apareció (los modos de la
Calculadora, live n2); después `ctrl_k` y `ctrl_f` (sólo si aparece un campo con foco o la tecla escribió un
aviso de búsqueda nuevo, «Q Buscar por nombre» en la biblioteca de Steam; si apareció otra cosa, Escape; si no
cambió nada, la siguiente tecla sin Escape); después
desplazar hasta tres veces la lista con más ítems (`input.scroll {index}`: `ScrollPattern` de ese control o la rueda
en su centro); sólo entonces el modelo. Un clic en algo visible que nombra el destino sin llegar (una tarjeta con su
nombre) no cierra BUSCAR: sigue con el buscador; si el clic fallido fue en el control del propio lugar, el lugar se
busca como lo ofrece la ventana, sólo cuando se nombró sin tipo («la pestaña de Gmail» no se busca). Dos o más
controles con el nombre del destino: el único ítem de navegación entre ellos (`TreeItem`/`ListItem`/`TabItem` en la
columna izquierda, no contenido) es el lugar; si no hay uno solo, se busca, nunca el clic en la palabra escrita. Una
frase que sólo menciona el nombre no es el lugar: un `Text`/`Group`/`Pane`/`Custom`/`Document` lo contiene sólo con ≤ 6
palabras más que él (Configuración: la descripción del proxy por «Wi-Fi»). Un menú abierto por el clic en el destino
(lo nuevo tras ese clic: `newText`, o `newTextAfterClick` si después sólo hubo clics fallidos; 2–8 líneas cortas de
palabras reales, sin ruido de OCR) elige la entrada que nombra el objetivo; si ninguna, la página propia del lugar
(«Página principal», «Inicio», «Home»…) y si no, la primera entrada sólo cuando el menú está en el árbol; nunca una
entrada que actúa (jugar, instalar, iniciar, ejecutar, comprar, enviar, unirse, desinstalar, eliminar). Nunca se
pulsa por su nombre el cuerpo de la ventana (un `Pane`/`Document`/`Window`/`Custom`/`Group` que cubre ≥ 80 %: «Chrome
Legacy Window»). Sin árbol, una palabra del host que empieza o termina con el lugar (≥ 5 letras) lo nombra
(«steamcommunity»: comunidad/community).

**Cuadro de búsqueda escrito (sin árbol).** Un clic en la línea OCR de una búsqueda no da por hecho el foco: se
escribe sólo si la mirada siguiente lo prueba (apareció un aviso de búsqueda nuevo, o la línea pulsada desapareció
con ≤ 3 líneas nuevas: el texto de ayuda se borró para el cursor) y ningún campo que no sea búsqueda informa el
teclado (un cuadro de mensaje, una contraseña, otro `Edit`); si no, la misión para con
`computer_use_search_focus_unproven` («no pude comprobar que el cuadro de búsqueda tomara el teclado, así que no
escribí nada»). El modelo tampoco escribe en «buscar X» con el teclado en otro campo. El Enter tras escribir en un
cuadro así va sin `target` sólo si lo tecleado se ve como la línea nueva del cuadro; si no, pregunta. En la
comprobación de una búsqueda, `text:X` con X tecleado en ella necesita X en dos sitios (título, control que no es
campo, líneas escritas): el cuadro que repite la consulta solo no prueba resultados (`OnlyTheQueryShows`).

**Texto libre con el teclado en el buscador (ronda 24b).** «escribir X» (no «buscar», ni «en el buscador», ni un
campo nombrado) con el foco en el buscador de la ventana pulsa antes la única caja de mensaje, o el único campo
editable que no sea buscador ni dirección; si el buscador es el único campo (un lanzador) se escribe ahí; con varios
campos y ninguna caja de mensaje, o sin ninguno legible en una ventana que nombra una caja de mensaje, decide el
modelo. Si la caja pulsada no toma el teclado, la misión para con `computer_use_field_not_focused`. El recibo del
tecleo guarda `intoSearch` y `otherField` (patrón compartido `computerUse.searchField`); el átomo
`stepDone:input.text.type:written` no se cumple con un tecleo `atCaret` en un buscador habiendo otro campo. «enviar»
tras «escribir X» se comprueba con `stepDone:input.key.press:enter&sent:X`: `sent:` mira la vista anterior al Enter
(`viewBeforeEnter`) y se cumple si el campo que tenía X se vació o X se ve más veces escrito; si X sigue en su campo
no se cumple; si la vista no lee ni campo ni texto, el Enter queda como recibo. La regla de «enviar» para con
`computer_use_text_not_in_composer` si el último texto fue al cursor en un buscador que sigue con el teclado. Un
Enter hacia la caja de mensaje deja de respaldar «envié» cuando el sub-objetivo de enviar no se cumplió. Revisión 1:
un campo que tenía X y se vació basta para darlo por enviado aunque otro campo (un buscador sucio) aún lo tenga; X
«se quedó» sólo en el campo que lo recibió (`into` del último tecleo, guardado en `viewBeforeEnter`). Leído sólo por
OCR, X visto antes del Enter y no más veces después con la vista cambiada (la caja vuelve a su placeholder, la
burbuja trae su hora) es ambiguo y el Enter queda como recibo; sólo una vista que el Enter no cambió, o que nunca
mostró X, dice que no se envió. Un Document es buscador sólo si su nombre entero es una etiqueta de búsqueda
(`computerUse.searchField.label`), de una línea y no el documento mayor: «Búsqueda de empleo» o «Ir a la playa»
son el documento de la persona; por palabra en el nombre sólo lo son un Edit o un ComboBox. Revisión 3: si el
buscador con el teclado contiene, como palabra, el último texto que esta misión tecleó en un buscador
(`lastTyped.intoSearch`), el chat no está probado y decide el modelo (un buscador sucio de otra misión sigue pulsando la
caja); una caja elegida que ya tiene texto (sin contar blancos, marcas de formato como U+FEFF ni su propio nombre) es
de la persona y no se pulsa por regla: decide el modelo.

**Página de inicio de un editor** (live v5/v6: Excel y Word abrieron en «Buenos días», con «Libro/Documento en
blanco», los recientes y «Buscar un archivo»; sus pestañas sólo existen con un documento abierto). Un objetivo de
pestaña («ir a / hacer clic en la pestaña X», fuera del navegador) cuya pestaña no está en la vista, en una ventana cuyo
título no nombra un documento (sin segmento « - ») y que ofrece **un** elemento para crear uno vacío (su nombre lleva
en blanco / blank / vacío / empty, ≤ 6 palabras, sin extensión, de un tipo accionable, nunca dentro de una lista,
cuadrícula o árbol salvo el de las ofertas —plantillas, nuevo, templates, new: `names_a_templates_list`—, nunca en una
vista de archivos —elementos con `itemType`, columnas Tamaño/Fecha/Tipo— ni en una lista de archivos propios;
palabras en `semantic/missions.names_a_blank_item`; revisión 2026-10-07: un archivo «Documento en blanco» del
Explorador recibía Enter): la persona crea primero el documento en blanco y después va a la pestaña. Enter cuando el
elemento con el foco de la ventana es la oferta misma, si no un clic en ella; el paso lleva `code: expects_title_change` y la App vuelve a mirar, sin OCR y hasta
8 s, hasta que cambia el título de la ventana. Crear un documento sin guardar es reversible y no toca ningún archivo;
nunca un reciente, nunca dos veces —pulsada o cliqueada la oferta, una página de inicio que sigue se dice, sin otro
paso— y nunca cuando el pedido nombra un archivo propio (`names_a_file`: un nombre con extensión, o
archivo/documento/libro/presentación no dichos como nuevos o en blanco; el nombre de la propia aplicación, «explorador
de archivos», no cuenta). En esos casos, o si la página
sigue tras crear, la mente devuelve `none` con `code: no_document_open` y la misión para con
`computer_use_no_document_open` («la aplicación está en su pantalla de inicio, sin ningún documento abierto»), sin
más clics. Sin oferta (o con dos) no se crea nada.

**Pantallas de puerta (v3, límites M2).** Una ventana de pocos controles (≤ 12) y líneas (≤ 15), sin `Document` ni
conversación y sin navegación (ningún `TabItem`, `MenuItem`, `MenuBar`, `TreeItem`, `ListItem` ni `DataItem`, ni dos
o más líneas de lugar en mayúsculas leídas por OCR, como «TIENDA», «BIBLIOTECA»), es una puerta (`app_gate` en
`computer_use.py`) cuando su título dice una cuenta o un inicio de sesión, una actualización en curso o un recurso que
no se encuentra (palabras es/en en `semantic/app_gates.py`), o cuando lo dice una línea o un control `Text`, `Button` o
`Hyperlink` que domina la pantalla (como mucho cuatro líneas más que no son el título, sus botones, sus campos ni otra
frase de puerta), o con un formulario de acceso (un campo nombrado como dirección o contraseña junto a una dirección
escrita). Una sola regla (`_gate_holds`) decide si la puerta para el objetivo, para el paso y para un `done` del
modelo encima de ella: no lo para si el pedido o el objetivo tratan de la puerta misma (iniciar sesión, la cuenta,
actualizar, con sus plurales y conjugaciones), si el objetivo nombra un control o una línea propia de la pantalla
(nunca el título, el nombre de la aplicación ni la frase de la puerta) o si este objetivo ya pulsó el control que
nombra. Si la para, antes del paso determinista y del modelo la mente pulsa una vez el control que la salta sin dar
nada (Ahora no, Omitir, Skip…) o devuelve `none` con `code: app_gate` y `arguments {evidence, gate, pressed?}`: el
texto exacto de la pantalla (el título primero, nunca una dirección), su clase (`account`, `updating`, `missing`) y el
control de salto pulsado, si lo hubo. La misión comprueba ese texto en la vista (`GateSeen`) y para con
`computer_use_app_gate`; `observed.gate {kind, text, pressed?}` llega al redactor y al suelo, que lo dicen con
`computerUse.appGate` y `computerUse.appGateTail` de `operation_floor.v1.json` («la aplicación muestra «…» y pide una
cuenta o un inicio de sesión; eso te toca a ti, así que no pulsé nada ahí», o «…; pulsé «Ahora no» y siguió ahí»).
Nunca se escriben credenciales. Contracasos: Word con documento y su botón «Iniciar sesión»; la Tienda de Steam con su
enlace; las descargas de Steam con un juego «Actualizando»; «Iniciar sesión de concentración» del Reloj.

**Límites con su causa (v3, M3).** Un final de misión parado en `computer_use_window_elevated` o
`computer_use_app_gate` sin las palabras de su causa (`computerUse.causeWords`; el nombre de la aplicación no cuenta)
se veta `cause_omitted`. Todo clic visible (`input.visible.click`, por identidad o por etiqueta) sobre una ventana
cuyo proceso corre como administrador falla antes de leer o pulsar con `window_elevated`. El código de parada de una
misión va en su propia línea de traza `computer_use.stop`; `computer_use.end` conserva los conteos aunque el código
no quepa en los 64 caracteres de la etiqueta.

**Modos.** «cambiá/pasá/switch to X» se leen como modo sólo con palabra de modo (modo, vista, mode, view) o con el
nombre propio de un modo (científica, estándar, programador, gráfica, conversor y sus nombres en inglés): `ir a X`;
lo demás lo lee el navegador, que quita el sustantivo de lugar («cambiá al canal general» → `ir a general`). «la vista
de detalles», «the details view» → `ir a detalles`; «vista previa» (sin «de») queda entera y se comprueba también por
X sola. «poné el modo X», «set it to X mode» → `activar modo X` (el interruptor así llamado si existe; si no, se elige
el modo como un lugar). Un modo con nombre propio se comprueba con `control:X:selected|title:X|page:X|header:X`
(`_mode_check`): la Calculadora no cambia título ni selección, su cabecera nueva dice «Modo de calculadora
Científica»; un clic sobre algo que nombra X no prueba nada (una tarjeta, una carpeta o un canal también lo llevan).
Un modo que ninguna ventana ofrece por su nombre («modo avión», «dark mode») se comprueba sólo con `control:modo
X:on` o `control:X:selected`, nunca página, título ni cabecera (la página «Modo avión» queda elegida y titulada con
el interruptor apagado). El adjetivo vale en los dos géneros («modo científico» / «Científica») sólo en modos: un
lugar conserva el género dicho, tampoco como errata. Un elemento «<lugar> <aplicación>» es el lugar («Científica
Calculadora» en la navegación de la Calculadora: la palabra del título de ≥ 4 letras al final se quita).

**Nombres en ambos idiomas.** Las apps que trae Windows se nombran en español e inglés (Paint, Terminal, El tiempo,
Vínculo móvil, Editor del Registro, Seguridad de Windows…; datos del catálogo), y «the Clock app», «la aplicación
Reloj», «la app de Configuración» nombran la app sin la palabra «app» (`catalog.application_name_without_frame`, también
en «in the X app go to …»). Los lugares de las ventanas tienen sus dos nombres en `semantic/missions._LABEL_ALIASES`
(cronómetro/stopwatch, alarmas, reloj mundial, colores, temas, pantalla de bloqueo, hora e idioma, rendimiento,
científica, este equipo…; ~60 pares nuevos el 2026-10-07): la comprobación acepta cualquiera de ellos y el prompt
del modelo dice que el control se elige por su significado. Los nombres de una app sólo cuentan para una palabra que
ningún lugar lleva («alarmas» nunca acepta el título «Reloj»); {inicio, start} y las palabras de menú que son actos
(archivo, vista, nuevo, abrir) no tienen otro nombre.

**Elemento de contenido elegido.** Tras un clic verificado en un elemento de contenido que quedó elegido sin que el
título nombre el lugar (un clic en «Descargas» del Explorador), el paso es Enter, con las condiciones de seguridad de
abajo. Contenido es un `ListItem`/`DataItem` fuera de la columna izquierda o, dentro de ella, uno con un mosaico del
mismo tamaño (±25 %) en su fila; un ítem de navegación junto a una tarjeta de la página sigue siendo navegación (el
Reloj: las alarmas de la página comparten fila con «Alarma»).

**En una conversación.** Una orden que nombra una aplicación instalada y se lee sola como un paso dentro de ella es su
propia misión, no la del decisor de contexto (`_self_contained_mission`: en caliente, el decisor elegía un clic suelto
o el cálculo tipado y fallaba). Un seguimiento sin aplicación sigue yendo al decisor; si su reformulación («Haz clic
en Configuración en Discord.») la lee el lector como un paso dentro de una aplicación y el decisor eligió una primitiva
de la misión (`MISSION_SUBSUMES`), el turno es `mission.computer.use` con esa reformulación como objetivo; una
operación tipada elegida por el decisor conserva su ruta (D21). Un seguimiento que no nombra aplicación y se lee solo como un paso con comprobación dentro de una («ahora ponela en modo científica», «and switch it to dark mode») ocurre en la aplicación en la que está la conversación —la que abrió o en la que trabajó el último pedido de la persona— como la orden de un turno «en <app>, <paso>», con las mismas comprobaciones del lector (`follow_up_in_application`; en caliente, v2-x12: el decisor lo cerró como límite y el motor corrió las palabras sueltas sin aplicación). Si el decisor eligió una operación tipada, ésa manda; sin aplicación en la conversación, con otro pedido en medio o con dos aplicaciones abiertas, decide él. Hereda sólo del pedido inmediato: cualquier otro mensaje en medio la corta salvo un sí/no pelado o un paso que ya heredó, y nunca reemplaza una pregunta, una charla o un límite que pregunta del decisor (r10). La aplicación es la dicha tras el último «en» («hacé
clic en Ajustes en Steam»), y ese corte sólo enmarca cláusulas de lugar (ir a, hacer clic, seleccionar, activar,
desactivar): «escribí Cuphead en el buscador en Steam» escribe «Cuphead».

**Objetivos libres.** Cuando el decisor elige el motor para un pedido que el lector no sabe partir,
`semantic.missions.free_form_arguments` usa las palabras de la persona tal cual como `goal` (≤ 512 bytes) y, como
`application`, el destino (`mission_destination`, v3 destino): la app que el pedido enmarca («en X», «abrí X», «con
X», en el orden dicho; nombre exacto o alias, errata, una palabra distintiva de un único nombre que no sea un
acompañante —sólo en el hueco de un verbo de abrir o como complemento «<cosa> de <palabra>» tras «en», nunca tras
«on», «con», «with» o «using»—, otro idioma por `similar` validado contra el catálogo; nunca un nombre entre comillas,
en una ruta o en un texto dictado: un verbo de escribir o poner, también con clítico, y «:» abren el texto hasta el
final), si no la de la conversación (`conversation_application`: la app en que terminó —su último marco— el último
pedido de la persona que la nombró, pasando por órdenes y sí/no, cortada por cualquier otro turno —y, con las
operaciones disponibles, por una orden que sirve una operación tipada propia; un pedido que abrió dos apps a la vez no
nombra ninguna—; un nombre dicho tras un verbo de ir en el pedido anterior, «andá a la configuración», y no leído allí
como marco de app, es ese lugar), si no una mencionada. Es la única lectura de la app de la conversación: la usan
también `follow_up_in_application` y la puerta de cobertura. Sin destino no lleva `application`: la misión no actúa
—ni tecla, ni texto, ni clic, ni scroll— sobre una ventana que no abrió ni le resolvieron
(`NoApplicationActs`, paro `computer_use_no_application`: la de delante es la de la persona) ni aprende ni reproduce
procedimiento. La excepción la nombra la persona: «en esta ventana …», «en la ventana activa/actual/de delante …», «in
this/the active window …» (`names_the_window_in_front`, fuera de un texto dictado y sin una app enmarcada) lleva
`frontWindow: true` y la ventana de delante es el destino. No hay todavía búsqueda de una ventana por las palabras de
su título. Sin `successCheck`: termina el `done` del modelo con evidencia en pantalla.

**Último recurso.** Una orden sobre el PC que el turno cerró como límite pasa al motor con las palabras de la persona
como objetivo (`semantic.missions.engine_can_try`), salvo preguntas, lugares fuera del PC, prohibiciones y objetivos
de borrar, formatear, desinstalar, comprar o pagar.

**Velocidad.** Paso del modelo con gramática GBNF de acto primero (`{"act":"click","i":12}`, ~10 tokens de salida en
vez de ~148, con caché de prompt: 4 s → 0,2–0,7 s en llama-server; en vivo 0,66–1,0 s con el prefill); 30 controles
ordenados por el objetivo (primero los que comparten palabras con él, luego enfocados, seleccionados y buscadores)
con la nota «N de M»; teclas por `SendInput` desde el propio proceso (46 ms la tecla en el provider, 67–79 ms el paso en vivo) y texto carácter a carácter a
35 ms (medido en el Bloc de notas de Windows 11: su editor lee cada tecla cuando llega a ella, así que más rápido
sale la última repetida —«lista: pan» → «lista:nnnn» a 3 ms, «lista:ppan» a 20 ms— y las teclas virtuales pierden
el Shift; desde 25 ms sale íntegro; un «escribí X» sólo cuenta si el campo enfocado que expone su valor muestra X); clic sin esperas fijas: el worker responde al
invocar y la postlectura pregunta el estado UIA cada 50 ms hasta 500 ms y compara la superficie desde 150 ms;
vista con captura y OCR en paralelo al árbol y OCR sólo cuando hace falta; un clic por etiqueta que ninguna etapa encuentra en una ventana que ya estaba vigila la ventana cada 200 ms y, si no cambió nada en 750 ms, responde «no está» sin otra pasada (antes 4,2–4,4 s; si cambia, mira otra vez enseguida); la vista que dio por cumplido un sub-objetivo es la primera del siguiente si no se hizo nada entre medio y es la misma aplicación (r8); 150 ms de asentamiento entre pasos (antes
400/1 200 ms); apertura de apps UWP verificada en su marco `ApplicationFrameHost` (antes agotaba 30 s); worker UIA
arrancado en segundo plano al iniciar el Core; sin rótulos de progreso escritos por el LLM durante una misión (el
estado se publica como «acting»); la ventana de un proceso se elige entre las usables (antes una vista atada al
proceso agotaba ocho reintentos, ~1,8 s, sobre el marco oculto de explorer.exe).

**Escribir y enviar.** El texto va con la grafía que dijo la persona, sin comillas. Sin foco en un campo de texto,
primero se pulsa el campo de mensaje o el único editable. «mandalo / envialo / send it» es el acto enviar: Enter con
`target: message_composer`, que `RiskPolicy` confirma siempre; un Enter en un campo de mensaje cuyo contenido la
pantalla no expone (`value` nulo, distinto de `""`) también cuenta como envío y se pregunta antes. Un buscador que
ya tiene otro texto se selecciona entero (`ctrl_a`, sólo en un campo de búsqueda) antes de escribir; uno que ya
tiene el nombre no se reescribe; un campo con texto que no es una búsqueda queda para el modelo. Un paso de
escritura es una sola línea.

**Voz del final** (`documentacion/00_IDENTIDAD.md`). El final de una misión lo dice quien actuó: primera persona,
informal y cálido, en el idioma de la persona, una frase; confirma el estado que la ventana muestra ahora (dónde
está, el valor pedido, dicho como lo escribe `seen.screen`), no los clics, teclas ni pasos, y nunca nombra la misión,
la evidencia, la comprobación, la pantalla ni la vista. Una tecla o un texto: sólo que está hecho en esa app, nunca
lo que causó. Un «ir a X» sólo fue a X: nunca dice que puso, creó, inició, encendió o cambió algo allí (el Reloj:
«Alarma» se contaba como una alarma puesta). El fallo se dice plano, con su causa (`seen.stoppedBecause`) y sin
disculpa; en una cadena no lograda, primero lo que no se pudo y su causa, después lo hecho, hasta dos frases.

**Seguridad v2 (revisión 2026-10-07).**
- La ventana de la aplicación es la que el provider resolvió para ella (`requested`), la de su ejecutable o la que
  lleva su nombre como palabras enteras en el último segmento « - » del título; nunca VS Code, Visual Studio, un
  editor, una terminal, una consola o BAXY si la persona no los nombró.
- También sin aplicación nombrada (la misión trabaja sobre la ventana de delante): la vista marca
  `window.protected` cuando su proceso es uno de esos y el pedido no lo nombró (`ProtectedFrom`, por proceso, nunca
  por título); la mente para sin preguntar al modelo y `BindToMissionWindow` no liga ningún acto a esa ventana
  (`computer_use_window_protected`, dicho en palabras de la persona).
- `input.key.press` e `input.text.type` llevan `window` (el hwnd de la vista sobre la que se decidieron), también al
  confirmar un paso tras el «sí» con BAXY delante. **v3 (punto 0, arreglo 1):** ligar significa que la entrega va
  dirigida a esa ventana (hwnd + proceso + hora de creación del proceso, comprobados antes de cada envío), no que
  tenga el frente. El texto va al campo `index` que la App toma de la vista (el enfocado o el del último clic):
  `ValuePattern.SetValue` sólo donde reemplazar equivale a teclear (escribible, no `Document` ni contraseña, vacío o
  todo seleccionado); si no, `EM_REPLACESEL` al hwnd de su control de edición (Edit/RichEdit) y, si lo ignora,
  `WM_CHAR` encolado; sin campo, el foco propio del hilo de la ventana si es un control de edición. Enter, Tab,
  flechas y teclas de edición van encoladas al foco de la ventana si es un control clásico. Lo que ningún mensaje
  alcanza (combinaciones `ctrl_*`, campos de Chromium/UWP/XAML sin valor escribible) sigue por teclado: el provider
  trae la ventana al frente o no envía nada; escribir se para si la ventana pierde el frente o se cancela. Un campo
  de solo lectura, de contraseña o deshabilitado (estilo `ES_READONLY`/`ES_PASSWORD` del control, o lo que dice su
  `ValuePattern`/UIA) no recibe nada por ninguna vía: `input_field_not_writable` antes de cualquier efecto. El recibo
  dice `method` y el frente leído antes y después de la entrega (`frontChanged`); si la entrega lo llevó a la ventana
  de la misión (o a la de su familia) desde una ventana de otro proceso, se le devuelve a esa ventana (`frontRestored`).
  **v3 (punto 1):** en Chromium/WebView2 el `SetValue` activa la ventana del campo (medido en vivo: con el editor
  delante, tras el `SetValue` el frente era la ventana del WebView2). Ese recibo (`frontChanged: true`) es una
  molestia aunque `frontRestored` la deshaga: el paso lo guarda (`frontChanged`, `frontRestored`) y la misión lo
  cuenta en la traza `computer_use.front` (nunca cero); sin frente, `WM_CHAR` no llega a ese campo, así que el
  teclado sólo es la alternativa dentro de una ráfaga de la concesión. Un texto con salto de línea o tabulador se rechaza. Si la misión nombra
  una aplicación y la vista no es su ventana (resuelta para ella o de su proceso adoptado), nada se pulsa, escribe,
  clica ni desplaza (`computer_use_window_not_application`, `BindToMissionWindow`); clic y desplazamiento van por el
  control de esa vista, sin hwnd.
- Enter o espacio sobre enviar/responder/comentar, o sobre un campo sin nombre que no expone su valor, llevan
  `target: message_composer`; también justo después de teclear si el foco es ilegible (ninguno, `Pane`, `Custom`:
  WhatsApp), y en el objetivo «apretar enter/espacio» con el foco ilegible (en una cadena lo escrito pudo ser otro
  sub-objetivo). En «buscar X» el Enter tras escribir va sin `target` sólo si el campo con el teclado es una búsqueda;
  si no, pregunta. Suprimir sobre un campo de texto lleva `target: text_field` (§2.1); el Supr de «ir a la dirección
  X» se arma desde la vista y sólo con el teclado en un campo de dirección (si no, no hay paso).
- Enter tras un clic que sólo eligió un elemento de contenido (sin `target`: no envía nada) sólo cuando el elemento es
  un contenedor: su `itemType` dice carpeta o unidad (si lo trae, decide solo), o la celda «Carpeta de archivos» /
  «File folder» está en su fila y dentro de él. Nunca en un archivo que se ejecuta (`.exe .msi .bat .cmd .ps1 .vbs .js
  .lnk .appx .msix .reg .hta .scr .cpl .jar .com .pif`), en una vista que ofrece desinstalar ni en un elemento que se
  llama quitar/eliminar/borrar.
- Procedimientos: Enter, espacio o Supr aprendidos no se repiten con su destino grabado (§5).
- Ninguna entrada al motor (lector, objetivo libre, último recurso) toma una meta de quitar, descartar, tirar a la
  papelera, cancelar o contratar una suscripción, alquilar, donar, vender, restablecer, limpiar, vaciar o salir de un
  servidor, además de las de borrar, formatear, desinstalar, comprar o pagar.
- Las metas de lugar («ir a», «buscar», «hacer clic en» sin tipo de interruptor) nunca pulsan un interruptor
  (casilla, opción, conmutador, deslizador, un control on/off o un botón cuyo nombre empieza por alternar, cambiar
  entre, toggle o switch between: «Alternar grados» pasó DEG a RAD): `changes_a_setting`, ni en los pasos sin modelo
  (se busca primero entre lo que no es interruptor, y ni el resultado ni la línea escrita eligen uno). Sólo un «hacé
  clic en X» cuyo X nombra ese interruptor lo pulsa: es orden de la persona. Una meta que activa o elige una cosa
  («activar modo programador», «seleccionar lápiz») sólo pulsa el interruptor que la nombra (y1: «Alternar grados»).
- Controles homónimos en una línea de descendencia son un objetivo; el campo que recibe texto sólo gana a su
  contenedor homónimo dentro de una caja (Group, Pane, Custom, ComboBox), nunca dentro de una fila: el Edit de
  renombrar de una fila del Explorador no se pulsa.

**Guardas.**
- Sin clics sobre un control que cubre ≥ 80 % de la ventana (`control_covers_window`); el modelo no repite por
  tercera vez un acto que no hizo aparecer texto nuevo (`no_progress`), y el bucle marca fallido un acto ya hecho
  desde la misma pantalla cuando la pantalla vuelve a ella (`computer_use_no_progress`). Un clic que no encontró su
  etiqueta no cuenta como acto que dejó la pantalla igual (e2: «blue» y «azul» antes de «Añil»).
- `page:` sólo juzga ventanas sin árbol de accesibilidad (≤ 1 control: CEF, canvas); donde hay controles, llegar es el
  lugar seleccionado, en el título, en el encabezado de la página (un texto, botón o vínculo con ese nombre exacto,
  todos los que lo llevan en la zona T o TL y últimos de su fila —una miga de pan acaba donde está la ventana; una
  barra de pestañas o de herramientas tiene más a la derecha—, y sólo tras un clic verificado o con el título
  nombrando el lugar: la primera mirada no es llegada; «Personalización > Colores») o un clic verificado en el
  control que lo nombra o lo abre («Abre Tu biblioteca»; un «<lugar> <aplicación>» cuenta como el lugar) tras el que
  la ventana cambió (≥ 40 % de controles nuevos) sin que la selección se moviera a otro elemento (un valor elegido
  dentro de la página alcanzada no cuenta como movida). Un clic verificado posterior en otro sitio deshace esa
  llegada (Steam: «BIBLIOTECA» y luego «TIENDA»); tras el clic en el lugar sólo cuenta como entrada de su menú un rótulo
  que no estaba escrito antes de ese clic, y un clic fallido que no lo nombra no cambia nada. En
  `page:` cuenta sólo un clic verificado que nombra el destino (o la entrada del menú que abrió), medido contra el
  texto de la vista **justo antes de ese clic**: llega si cambió más de la mitad de las líneas. Una ventana que quedó
  igual tras el clic **no** es llegada (la página puede no estar dibujada todavía); un lugar ya abierto lo dice su
  selección, su título o, sin árbol, su dirección escrita.
- Lo tecleado se juzga en pantalla, nunca por los recibos de las teclas: el campo enfocado que expone su valor debe
  mostrarlo; un valor cortado (120 caracteres) es desconocido. El campo que el paso nombró (`field`) decide antes que
  el foco. Con un foco que no expone su contenido (un panel del marco, el editor de Discord), lo muestra un campo de
  la vista que lo contiene más veces que en la vista de justo antes del paso o, si no, el texto escrito de la vista
  (su comienzo o su final, sólo letras y dígitos, con las líneas unidas) más veces que antes: lo que ya estaba en
  pantalla no prueba nada (revisión r2: el nombre de un contacto que ya estaba en la lista de chats). Una contraseña o una vista que no escribe nada
  deja en pie las teclas aceptadas (cu-v3 texto-webview, wa-1: el marco de WhatsApp aceptó las teclas y el buscador
  siguió vacío). «Escribí X en el buscador / in the search box» es el cuadro de búsqueda de la vista con X (nunca la
  barra de direcciones), juzgado tras el acto (`stepDone`), nunca X con su lugar; «en el campo N / in the N field» se
  separa sólo si la vista tiene un campo escribible llamado N (o su par es/en): la frase sola no distingue un campo de
  un lugar del mundo («nos vemos en el campo de fútbol»), y un campo con contenido (un borrador) se pulsa y recibe el
  texto en el cursor, nunca reemplazado. El eco de lo que BAXY escribió (un buscador o su
  sugerencia) nunca cumple `control:X`, y lo que un campo contiene no prueba llegada. Lo tecleado nunca es evidencia:
  el `done` del modelo que cita lo escrito (o lo contiene, salvo en «escribir») se rechaza en la mente
  (`evidence_not_visible`) y en la
  App (§4.3, eco de la consulta); Steam citaba «Cuphead» del buscador de la tienda.
  Tampoco cumple `stepDone:input.visible.click:X` un clic en un texto, campo o documento que repite dentro de una
  frase más larga lo que el sub-objetivo tecleó antes en una búsqueda («No hay resultados para «X»»,
  `ClickEchoesQuery`; medido en Configuración, v11 2026-10-07); un resultado o un ítem sí.
- Un clic aprendido (procedimiento) se fija al único control de la vista actual con su nombre y se pulsa por
  identidad; tras un clic fallido el paso del objetivo se busca de nuevo en la vista, nunca el mismo acto.
- Las ventanas del shell (escritorio, barra de tareas) nunca son la ventana de una aplicación.
- **Familia de procesos (v3, punto 1).** La superficie de una app es la ventana visible de nivel superior de un
  proceso **descendiente** suyo (arrancado después que ella) que está encima de su ventana, cubre al menos el 90 %,
  no la excede en más de un 2 % y **no es una ventana de aplicación propia** (sin botón propio en la barra de tareas
  ni en Alt-Tab: ni `WS_EX_APPWINDOW` ni, sin dueño, falta de `WS_EX_TOOLWINDOW`/`WS_EX_NOACTIVATE`;
  `IsApplicationWindow`; medido: la ventana del WebView2 lleva `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`, `0x08280080`,
  mientras navegadores y editor sin dueño, `0x00200100`, y el ayudante web de un iniciador, con `WS_EX_APPWINDOW`,
  sí son ventanas propias) (WebView2, CEF, Electron; sin nombrar apps): medido en vivo, el marco WinUI de un
  cliente de mensajería exponía 8 elementos y ningún campo, y su contenido era una ventana `Chrome_WidgetWin_1` de
  un proceso `msedgewebview2` hijo, sin dueño, con todo el árbol (81 elementos, el buscador entre ellos). Lo aplican
  `ResolveProcessWindowAsync` y `ResolveTitledWindowAsync`; nunca para las ventanas del shell (todo lo que la persona
  arranca desciende de él), ni hacia un proceso protegido o el propio. La vista dice `window.family` (el pid de la
  app primero, luego sus descendientes); la misión guarda el pid de la app y `family` sólo si empieza por él
  (`AdoptWindow`), y `BindToMissionWindow`/`ShowsTheApplication` aceptan un `processId` de esa familia y de ningún
  otro proceso. La ventana de la app y su superficie forman un par: el frente de una vale por la otra
  (`ForegroundIs`, `Holds`, medido: teclas con el marco delante llegaron al campo del hijo), comprobado por hwnd y
  pid de cada una en cada consulta. Una ventana de un descendiente que cubre así la ventana no la tapa
  (`CoveringWindow`); una de un proceso que arrancó a la app (el shell, un editor) sí. Con la superficie hija, el
  marco vacío (0 accionables) ya no es lo que se mira, así que no agota la espera de arranque. La geometría sola no
  distingue el contenido de una ventana propia que un proceso de la app abrió (revisión: un navegador que la app
  arrancó, maximizado como ella; un juego a pantalla completa sobre su iniciador maximizado con la barra oculta,
  1920×1080 sobre 1920×1078): esas ventanas tienen botón propio, nunca son la superficie ni entran en `family`, y
  `CoveringWindow` las trata como tapa (una sola regla, `IsContentOf`).
- Una app empaquetada que se dibuja dentro de un marco `ApplicationFrameHost` tiene ese marco por ventana; sus
  ventanas de nivel superior son sus emergentes (medido en vivo: el historial de una búsqueda, «Host de ventanas
  emergentes», se tomó por la app, la vista perdió el campo y se pulsó una entrada del historial). La vista de un
  marco nombra el proceso de la app que aloja (`ViewProcess`), nunca el `ApplicationFrameHost` que comparten todas
  (Configuración y la Tienda): la misión nunca adopta el pid del anfitrión, que la llevaría al marco de otra app
  (revisión 2026-10-07). Un control es
  una búsqueda si lo dice su nombre antes de la ayuda que trae («speedtest. Presione la tecla Suprimir…» no lo es), y
  un campo que el recibo del clic dice pulsado conserva el cursor aunque la vista siguiente ya no lo liste: se
  escribe, y el Enter sin un campo de búsqueda visible con el teclado pregunta.
- Una app abierta en frío se vuelve a mirar hasta **20 s** (`StartWait`, unificado con el código; medido: el
  iniciador de un juego mostraba su pantalla de arranque 11 s después de aparecer su ventana) mientras parezca de
  arranque (≤ 1 control accionable —un marco, un panel o una barra de dirección de sólo lectura no cuentan— y ≤ 5
  líneas) o mientras **cambie**: cada mirada se compara con la última que difirió, tomada al menos 400 ms antes
  (`StartSettle`): ventana, controles, texto escrito y, sólo si no hay controles ni texto, el hash de la imagen (un
  cursor que parpadea cambia la imagen de una ventana ya quieta). Arrancó cuando dos miradas así coinciden (v3,
  punto 1, medido sin árbol: 2 líneas a 4,5 s, 16 a 8,2 s, 35 desde 11,8 s; la regla anterior tomaba la de 16). Entre
  miradas se espera lo que falte para esos 400 ms. Cada mirada del arranque lleva `starting`: si la apertura anotada
  es la de esa app (la última apertura que dejó delante la ventana de la persona; toda apertura nueva olvida la
  anterior) y la app (su proceso o uno que arrancó) tomó el frente sola —BAXY no lo tomó a propósito desde la
  apertura y el frente pasó a la app entre la mirada anterior y esta sin entrada de la persona; si la persona la
  trajo, se queda delante todo el arranque—, el frente vuelve a la ventana de la persona (`ForegroundHandBack`) y la vista dice
  `window.frontReturned`; la misión lo cuenta (`frontReturnedAtStart`, traza `computer_use.front`). Medido: el
  iniciador se activó al crear su ventana y al maximizarse (4,5 s y 6,3 s), fuera de la guarda de 3 s de la apertura.
- Un `none` del modelo sobre la vista tomada justo tras un acto verificado que cambió la pantalla, cuando esa vista
  lista menos controles que la pantalla desde la que se actuó (la pantalla se desmontó: medido en vivo, 185 ms tras el
  Enter de una búsqueda la página de resultados listaba 17 de 52 controles, un esqueleto de marcadores), no para la
  misión todavía: una vez por acto se vuelve a mirar cada 400 ms, hasta 6 veces, hasta que la vista cambia y se queda
  quieta, y el bucle mira y decide de nuevo; si no cambió, el `none` vale (`computer_use_no_step_visible`).
- Una ventana de administrador (`window.elevated`) para la misión con `computer_use_window_elevated`, dicho con esa
  causa. Si el manifiesto de su programa dice `highestAvailable` sin `autoElevate` (`window.reopensUnraised`, medido
  en las consolas), para con `computer_use_window_elevated_reopenable`, que además ofrece reabrirla sin permisos de
  administrador; un programa que se vuelve a elevar solo (el Administrador de tareas) no lleva la oferta.
  `cu-v3-elevacion`: antes del primer paso, una ventana elevada con `window.reopensUnraised` no para: el primer paso
  es `app.open` (regla de la mente), y el proveedor reusa una copia de la aplicación que no esté elevada o, si no hay,
  abre una nueva con los derechos de la persona; nunca reusa la elevada (que BAXY no puede cerrar: Windows lo niega,
  medido). Cualquier otra decisión sobre la ventana elevada (un `done` citando lo que leyó el OCR, un clic), una
  misión sin aplicación nombrada o un paso posterior paran con el límite (`ElevatedViewAllows`). La vista cambia la
  ventana elevada por una legible sólo si ésta es del mismo ejecutable y no está elevada (`PreferReadableCopy`); nunca
  por otra ventana que sólo la nombra en el título (una carpeta «Administrador de tareas»).
- Todo `app.open` (`forControl`) abre como la persona (`__COMPAT_LAYER=RunAsInvoker`, fuera del Job del Core, sin
  heredar handles) un programa que Windows elevaría sin pedirlo; sólo un pedido que pide derechos de administrador
  («como administrador», «as admin», «consola elevada», datos `administratorAsked` de `operation_floor.v1.json`; nunca
  «elevado/elevated» suelto, que puede ser «un consumo elevado») sigue el camino del shell. `forControl` lo decide la
  App sólo por el pedido: el valor que escriba el modelo extractor se reemplaza. Medido en vivo (2026-10-08, UAC sin
  aviso): por el shell Servicios, Visor de eventos y Programador de tareas quedan elevados; con `mmc.exe <consola.msc>`
  y RunAsInvoker, sin elevar. El Administrador de tareas (`asInvoker` + `autoElevate`) y el Monitor de recursos
  (`perfmon /res`) se relanzan elevados desde su código aunque se abran así (también con un token SAFER de usuario
  normal): son un límite honesto. Medido otra vez en vivo (2026-10-09, `cu-v3-errata-elev-vivo`, CreateProcess con
  RunAsInvoker como el producto y el arnés, nivel de integridad leído del token): `Taskmgr.exe` sale antes de 0,4 s y
  su hijo `Taskmgr.exe` corre en IL alta (0x3000, `TokenElevation` 1); `perfmon.exe /res` y `resmon.exe` arrancan en
  IL media (0x2000) y sus hijos `perfmon.exe` corren en IL alta; `mmc.exe eventvwr.msc` queda en IL media. Windows no
  permite abrir esos dos sin elevar en una cuenta de administrador: ni el producto ni el arnés los elevan, se elevan
  solos. Lo que sí queda en manos de BAXY: una misión sobre ellos para con `computer_use_window_elevated` sin pasos
  (0 pasos, < 1 s, medido en r15b: v3-20, v3-21, v3-70, v3-71), y si la orden pide abrirlo, el único paso es esa
  apertura pedida. La copia elevada nace del lanzador efímero, que el registrador del arnés (cada 0,3 s) puede no ver:
  en r15b el `Taskmgr` que BAXY abrió en v3-22 quedó `sin_procedencia`, no se cerró y tapó (siempre encima) v3-72,
  v3-20, v3-21, v3-23 y v3-26. El libro del lote toma ahora como suyo el proceso que el diario de BAXY nombra en un
  `app.open` completado sin reusar copia (`Get-AbiertosPorBaxy`, `alreadyRunning:false`, `processId`) y lo cierra
  con `Stop-ProcesoElevado`.
- Alcance (revisión de `cu-v3-elevacion`): la regla es el manifiesto, no las consolas. Medido sobre los manifiestos
  de `C:\Windows` y `System32` de este PC: `highestAvailable` sin `autoElevate` llevan `mmc.exe` (todas las `.msc`),
  `regedit.exe`/`regedt32.exe`, `DXCpl.exe`, `appverif.exe` y `SpaceAgent.exe`; con `autoElevate` (siguen elevándose)
  `perfmon.exe`, `dfrgui.exe`, `eventvwr.exe`, `odbcad32.exe`, `ComputerDefaults.exe` y otros. Así, «abre el editor
  del registro» abre ahora regedit sin elevar (lee todo; escribir en `HKLM` lo niega Windows): antes, con este UAC, salía
  elevado. Para cambiar el sistema hay que pedirlo «como administrador». Una copia que la persona abrió «como
  administrador» en un turno anterior no se usa en una misión: ésta reusa o abre una copia sin elevar.
- Un control sin patrón invocable ni punto clicable (Electron) se pulsa en el centro de su rectángulo.
- Un procedimiento que deja de cambiar la pantalla se abandona y sigue el bucle; la misión no.
- `RiskPolicy` confirma también publicar, responder, comentar, compartir, unirse, comprar, pagar, borrar y
  desinstalar; un límite conocido del catálogo no anula una misión probada dentro de una app instalada.

**Lectura del pedido v2 (`semantic/missions.py`).** Cada cláusula de hacer trae su comprobación determinista; una
cadena con una cláusula sin comprobación sigue siendo del decisor. Familias y comprobación:

| Cláusula | Objetivo | `successCheck` |
|---|---|---|
| creá una carpeta llamada X / create a folder named X | `crear carpeta X` | `control:=X&stepDone:input.text.type:X` |
| renombrá A a B / rename A to B | `renombrar A a B` | `control:=B&stepDone:input.text.type:B` |
| andá a X / go to X | `ir a X` | `control:X:current\|title:X\|page:X` (+ nombres en el otro idioma) y al final `mark:X` por cada nombre; un clic que sólo eligió un elemento de contenido sigue con Enter. Cumplido en la primera mirada sin ningún acto (salvo abrir la app; un paso fallido con `effectUncertain` —pulsó pero su post-lectura no se sostuvo— es un acto): no aprende procedimiento y el final es «Ya estás en «X».» (`computerUse.placeAlready`); el rótulo marcado viaja en `screen.values` como elegido. La parada de respaldo `computer_use_already_there_unconfirmed` no se dice si la fila marca otro rótulo |
| elegí el lápiz / el color rojo / pick the red color | `seleccionar X` | `control:=X:selected\|control:=X:on\|stepDone:input.visible.click:=X` (+ nombres en el otro idioma); un color básico suma `stepDone:input.visible.click:=T` por cada tono de su familia (`semantic/colours.py`: azul → añil, índigo, turquesa…), porque una paleta puede no tenerlo por su nombre |
| buscá X / search for X | `buscar X` | `title:X&stepDone:input.key.press:enter\|title:X&stepDone:input.visible.click:X\|stepDone:input.text.type&stepDone:input.key.press:enter&text:X` (los resultados en pantalla son la meta) |
| cambiá a científica / pasá a la vista X / switch to X mode | `ir a X` | `control:X:selected\|title:X\|page:X\|header:X` (+ nombres en el otro idioma y el otro género) y al final `mark:X` por cada nombre |
| poné el modo X / set it to X mode | `activar modo X` | `control:modo X:on` + la de arriba si X es un modo con nombre propio; si no, `control:X:selected` |
| poné la primera / play the first one / ponelo | `reproducir …` | `control:pausa&stepDone:input.visible.click` (y `pause`, y con tecla) |
| copiá / pegá / deshacé / seleccioná todo | `apretar ctrl c` … | la tecla o el clic en su control |
| abrí una pestaña nueva | `apretar ctrl t` | `stepDone:input.key.press:ctrl_t` |
| andá a es.wikipedia.org | `ir a la direccion …` (ctrl_l, texto, Supr, Enter: Supr quita la página del historial con que la barra completa la dirección) | `title:wikipedia` |
| abrí la sección Historia | `ir a historia` | lo de `ir a` + el clic verificado en la sección |
| calculá 12 por 7 / multiply 6 by 7 | `calcular 12 × 7` | la de calcular |

En una cadena el verbo puede decirse una vez («elegí el lápiz y después el color rojo», «go to System, then
Display», «hacé clic en Insertar y después en Tabla»), un pronombre o un lugar genérico retoma lo último nombrado
(«buscá Hades y abrilo», «creá la carpeta X y entrá», «buscá a Mamá y abrí el chat»), una cláusula que nombra otra
aplicación cambia la del paso («… y pegalo en el Bloc de notas») y una pregunta final («… y decime si el modo es
claro u oscuro», y con un verbo de decir también la cosa sola: «… y decime el volumen», «and tell me the volume»)
no es sub-objetivo: va al final del `goal` tras `; y responder: ` y el final la contesta sólo con
`seen.screen`/`seen.evidence`; nunca dentro del texto dictado (entre comillas abiertas, o tras «escribí:» sin
comillas, que llega hasta el final): «escribí "pasá y decime el horario"» lo teclea entero. Las comillas que delimitan un nombre («haz clic en «Sistema»», la reformulación
del decisor de contexto) no son parte de él. Nunca es misión un pedido que ordena borrar, vaciar, formatear, desinstalar, comprar
o pagar (lo tecleado no cuenta). Tipado contra motor: en una cadena sólo las operaciones tipadas que no son
primitivas del motor cubren sub-objetivos; un cálculo dicho dentro de una aplicación se hace en ella.

El paso de tecleo guarda en qué campo se escribió (`into`); el átomo `control:` descarta lo tecleado sólo si se
tecleó en una búsqueda, una barra de direcciones o un campo sin nombre (el eco de sus sugerencias), no el nombre
escrito en la caja de un elemento que se crea o se renombra. Corpus: `tests/test_computer_use_corpus.py`.

En un navegador (un campo de dirección que contiene una dirección web) la búsqueda y sus resultados son los de la
página: controles dentro del documento más grande y listados después de él; la pestaña de búsqueda de pestañas, los
marcadores y la barra lateral son del marco, y `ctrl_k` (la búsqueda web de la barra) no se usa, sólo `ctrl_f`. Mientras
la página no está expuesta (ningún documento de un cuarto de la ventana) la App vuelve a mirar, hasta 6 veces cada
400 ms, una sola vez por título. El modelo no puede pulsar un control que abre otra pestaña o ventana si el objetivo
no lo pide (`opens_elsewhere`).

## 8. Versión 3, punto 3: ventanas sin árbol e íconos sin texto (sin modelo de visión)

### 8.1 Nombre de respaldo (construido)

Un control accionable sin `Name` UIA no se descarta. `DesktopUiaWorker.ps1` cachea `HelpText`, `AutomationId` y
`LabeledBy` en la misma llamada que el resto (`Get-ShownName`) y lo nombra, en este orden:

1. su **texto de ayuda** (`HelpText`: el ToolTip de texto de WPF se publica ahí; Chromium pone el `title` en el
   nombre y `aria-describedby` en la descripción);
2. el **nombre de su rótulo** (`LabeledBy`: un campo de formulario etiquetado por su `Text`);
3. su **AutomationId legible** (`Get-ReadableId`): CamelCase y separadores partidos en palabras, sin la palabra final
   que sólo repite el tipo («SettingsButton» en un `Button` → «Settings»; «NewTabMenuItem» → «New Tab»; el prefijo de
   plantilla de WPF se quita: «PART_CloseButton» → «Close»). No nombran nada los ids que dicen qué es o dónde está el
   control y no qué hace: un número, un GUID, un hash (hexadecimal, o letras y cifras alternadas: «a8Xk2Lq9»), un id
   sin una palabra de dos letras, un nombre calificado con «.» («System.Windows.Controls.Button»), la clase del propio
   control (`ClassName`, también cacheada: «ListViewItem»), el nombre por omisión de un diseñador o un ordinal (una
   palabra en minúscula o el propio tipo seguidos de un número: «button1», «textBox1», «Button1», «uid_12»), un id
   generado con una letra suelta («radix-:r3:») y uno con más números que palabras («Item_1_2»). «Page2» → «Page 2» y
   «CloseWindowButton» → «Close Window» sí nombran.

El control lleva `nameSource` (`helpText`, `labeledBy`, `automationId`); sin él, el nombre es el propio. Un `Name`
propio nunca se sustituye, y un `Pane`/`Group`/`Custom` sin nombre sigue fuera (no es accionable). El clic por
etiqueta (`Find-Named`), el clic por índice (comprobación de la etiqueta), la línea de descendencia y `find`
comparan ese mismo nombre, así que lo que la vista lista es lo que se puede pulsar. `window.focused` lleva también
`nameSource`. Para el riesgo, un nombre de respaldo **no es un nombre propio**: la mente (`_own_name`) no lo usa para
liberar un paso (un campo con respaldo cuenta como campo sin nombre en `_composer_with_text`, así que Enter tras
escribir pregunta; no lo vuelve búsqueda en `_is_search_field` ni dirección en `_keyboard_on_address_field`), y sólo
puede hacer preguntar más (un respaldo que suena a caja de mensaje marca `message_composer`). Pruebas:
`ComputerUseFallbackNameTests`, `tests/test_cu_z_mind_safety.py`. Medida: `scripts/cu_live/cobertura_sin_arbol.ps1` (por ventana:
accionables, sin nombre, recuperados por cada fuente, antes/después; sólo lectura, sin foco).

### 8.2 Tooltip dentro de una pausa (construido: `WindowsVisibleTooltipLocator`)

Etapa `tooltip` de la cascada del clic, **entre OCR y visión**, cuando la etiqueta que nombra la orden no la encontró
ni UIA ni OCR. Corre **una vez por clic, en la última mirada** del bucle de espera (cuando expira la espera de la
etiqueta, cuando la ventana se queda quieta o en el tope de la app abierta; una página que aún se dibuja le enseña la
etiqueta antes a otra mirada, y su tiempo no se descuenta de esa espera) y **sólo con ventana ligada** (la de la
misión `window`, la de la app recién abierta o la de la vista cuya identidad caducó): nunca en la ventana que la persona
tiene delante fuera de una misión, y nunca en una ventana protegida (`ProtectedFrom`: editor, terminal, BAXY).

1. **Recordado antes.** Las etiquetas leídas se guardan en `<data root>/computer-use/tooltip-labels.v1.json` por firma
   de ventana (proceso, clase, tamaño en tramos de 160 px) y lugar relativo redondeado a 8 px, 30 días, con la **huella**
   del lugar al leerlo (`TooltipImage.Print`: aHash 8×8 y gris medio) y la caja de su tooltip. La firma es amplia (todos
   los sitios o canales de una ventana la comparten), así que un lugar recordado vale sólo si su huella coincide con la
   captura actual (`SamePrint`: ≤ 6 celdas distintas, gris ±24); si no, se olvida y su control se vuelve a pasar. Se
   pulsa con `at` + `remembered` y el tamaño del lugar: si en el punto hay un control de hasta 4 veces ese área con
   otro nombre (`Test-NamedOther`), el worker responde `visible_point_named_other` (`PointPressOutcome.Refused`): ni
   patrón ni puntero; la etapa olvida el lugar y vuelve a pasar el cursor una vez. Un clic en un lugar recordado que no
   cambia nada lo olvida; un hover que lee otra etiqueta en el mismo lugar la sustituye.
2. **Candidatos.** Los accionables que siguen sin nombre tras §8.1 (comando del worker
   `{"cmd":"unnamed","hwnd":H,"limit":24}`: no campos, con rectángulo de 6–200 px). Si no hay ninguno y el árbol no
   tiene más de un nodo con nombre (ventana sin árbol), regiones con forma de ícono de la captura
   (`TooltipImage.IconCandidates`, sin modelo y en C#: bordes fuera de las líneas OCR, unidos por un píxel, formas de
   12–64 px con proporción 0,5–2 que no tocan el borde ni son un bloque lleno; primero las más cercanas a un borde de la
   ventana, donde están las barras). Se saltan los lugares cuya etiqueta ya se conoce. Tope: 6 candidatos y 9 s por
   reloj real, **listado incluido**: el listado recibe como mucho el presupuesto, la espera de la pausa se corta al
   agotarse y cada sondeo lleva el tiempo que queda.
3. **Ráfaga por candidato.** `ForegroundLease` (vía `ScreenPointer.AcquireAsync`): espera ≥ 500 ms sin input de la
   persona (tope 8 s → `input_user_not_paused`: se deja todo), trae la ventana. Sólo si la ventana está delante y es la
   que está bajo el punto (`WindowFromPoint` → raíz), el cursor se pone en el centro del candidato con un último paso
   de 1 px y se sondea cada 100 ms hasta 700 ms el comando `{"cmd":"tooltips","hwnd":H,"pids":[P]}`: un tooltip
   **nuevo** (que no estaba antes del hover) de primer nivel del proceso (`ToolTip`, el `ToolTip` dentro de un Popup, o
   una ventana cuya clase dice tooltip) o un `ToolTip` dentro de la ventana (una página con `role=tooltip`), **cuyo
   rectángulo corta la franja de 480×300 alrededor del candidato** (uno lejos es de otro control) → `nameSource:
   tooltipUia`. Un sondeo sin respuesta a tiempo deja de sondear: decide la captura.
4. **Sin tooltip por UIA** (dibujado dentro de la ventana): captura antes y después dentro de la misma ráfaga, caja de
   lo que cambió en una franja de 480×300 alrededor del cursor sin el resalte del propio control
   (`TooltipImage.ChangedBox`; si cambió más de 480×200 es la página, no un tooltip), y OCR de esa caja después y antes:
   sólo las líneas nuevas (`TooltipImage.NewText`) → `nameSource: tooltipOcr`. La ráfaga se devuelve justo tras la
   captura «después»: el OCR corre con el cursor y el frente ya devueltos.
5. **Restaurar.** Cada ráfaga se devuelve al terminar su candidato (frente, orden y cursor, salvo que la persona lo
   moviera). Si la persona actúa durante la ráfaga, se corta en el acto y no se aprende nada de ese candidato ni se
   sigue con los demás. Nunca un clic mientras se pasa el cursor.
6. **Clic.** El control cuyo tooltip nombra la etiqueta (`LabelNames`) se pulsa como un punto que encontró el OCR
   (`LocatedPointPress`: por el árbol en el punto si algo ahí tiene patrón y nombre; si no, el puntero en otra ráfaga
   tras otra pausa) y se prueba por cambio de la ventana **fuera de las marcas del hover** (hasta 1,5 s;
   `TooltipImage.ChangedOutside`: ≥ 20 píxeles fuera del control inflado 6 px y de la caja de su tooltip, o de la
   franja si no se conoce; con el puntero el cursor queda sobre el ícono y su tooltip vuelve aunque el clic no haga
   nada). Una etiqueta recién leída se pulsa cuando su tooltip ya no está por UIA y dos capturas seguidas son iguales.
   Recibo: `cascadeStage: tooltip`, `name` (la etiqueta del tooltip), `nameSource`, `learnedBefore`, `waitedMs`,
   `restored`.

Pruebas: `ComputerUseTooltipTests` (funciones puras, la etapa con escritorio/worker/prensa falsos, el orden en la cascada
y las funciones del worker por su árbol sintáctico). En vivo: `TooltipHoverLiveCheck` (Explicit,
`BAXY_TOOLTIP_LIVE_CHECK=self,<proceso>,…`), que sólo pasa el cursor (salvo en su propia ventana, donde también pulsa).

Un accionable del árbol recién leído se pulsa con su identidad (`at` con `controlId`: ese control del punto cuenta como
nombrado), así que su patrón lo pulsa sin ratón; uno recordado de otra sesión o una región dibujada va por el punto.
Pendiente: la vista (`input.visible.controls`) aún no lista los nombres aprendidos.

### 8.3 Accesibilidad forzada de Chromium/CEF (investigado; no se construye)

- **Chromium, Electron y WebView2 ya la activan solos** cuando un cliente UIA pregunta (`WM_GETOBJECT`): Discord da su
  árbol completo y WebView2 también. No hace falta ninguna opción.
- **Steam no**: su CEF tiene la activación a demanda apagada (texto7 de la ronda 0: 3 nodos, IAccessible vacío tras
  `WM_GETOBJECT`). `libcef.dll` reconoce `force-renderer-accessibility`, pero `steam.exe` lanza `steamwebhelper.exe`
  con su propia línea de comandos (comprobada: sin opción de accesibilidad), así que un `--force-renderer-accessibility`
  dado al lanzador no llega al proceso CEF. Lo que Steam acepta es su opción privada `-cef-force-accessibility`
  (presente en `steam.exe` y `steamclient64.dll`): es de una app, no un mecanismo general.
- **Inyectar la opción de Chromium al abrir** apps que traen `libcef.dll` o Electron no es general ni seguro: BAXY
  abre las apps por `explorer.exe shell:AppsFolder\<AUMID>` (`WindowsInstalledApplicationOpenProvider`), que no lleva
  argumentos; muchas arrancan por un lanzador propio (que no pasa opciones de Chromium al hijo) y las de una sola
  instancia ignoran las opciones de un segundo arranque; un argumento desconocido puede leerse como archivo o URL.
- **Queda como decisión del dueño** (`DECISION_VISION_V3`): arrancar su Steam una vez con `-cef-force-accessibility`
  (opciones de inicio o acceso directo; reinicia Steam, no toca datos). Con eso §8.1 y el resto del motor leen Steam
  como cualquier ventana Chromium.
