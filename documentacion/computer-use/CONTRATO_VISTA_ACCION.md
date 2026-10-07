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

- **Orden y selección.** Primero los accionables (`Button, MenuItem, ListItem, TabItem,
  Hyperlink, CheckBox, RadioButton, Edit, ComboBox, TreeItem, SplitButton, Slider,
  Document`), luego el resto hasta `limit`. Sólo elementos habilitados, con nombre y en
  pantalla. Un mismo `kind|name` repetido se lista **una vez** con `"repeated": n`; el clic por
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
| pulsar | `input.visible.click` | `label` (obligatorio), `index?` (de la vista), `controlId?` (RuntimeId de la vista) | `selected` \| `absentOrDisabled` \| `surfaceChanged`; con índice/id, el nombre del control debe coincidir con `label` |
| escribir | `input.text.type` | `text`, `window?` (la ventana de la misión, v2) | SendInput aceptado + el control enfocado no es `password`; en una misión, el campo muestra el texto (§7) |
| tecla | `input.key.press` | `key` (enum cerrado, ahora con combos `ctrl_a ctrl_c ctrl_f ctrl_k ctrl_t ctrl_w ctrl_z f5`), `target?` (`message_composer` \| `text_field`), `window?` (la ventana de la misión, v2) | SendInput aceptado en esa ventana delante |
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

## 3. Grounding: de lo que dijo la persona a un control

Orden fijo; el primero que resuelve gana; con dos candidatos se pregunta, nunca se adivina.

1. **Texto.** Nombre UIA, `aria-label` (es el nombre UIA en Electron/Chromium) o línea OCR,
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
2. **Recordar.** Si hay un procedimiento guardado para `(application, goal normalizado)`
   (§5), se ejecuta su siguiente paso sin modelo; si su verificación falla o la vista no
   trae lo que el paso espera, se abandona el procedimiento y se pasa al modelo.
3. **Decidir.** `computer.use.step` a la mente (§4.4). Primero lo que el objetivo dicta sin
   modelo (`computer_use.deterministic_step`): la aplicación pedida no está delante →
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
4. **Actuar.** La primitiva va al Kernel como operación con sus argumentos; el Kernel
   autoriza (§2.1), el provider ejecuta y verifica.
5. **Registrar.** El paso queda en la misión con `{operation, args, ok, error, changed,
   window}` y en el journal; el hito se narra a la persona («Paso 3: clic en Biblioteca»)
   cada ≤ 3 s.
6. **Parar** cuando: `successCheck` se cumple (o el modelo dice `done` con evidencia
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
         | "title:" needle              # título de la ventana de delante
         | "process:" name              # proceso de la ventana de delante
         | "count:" kind op N           # número de controles de ese kind (op: <= < == >= >)
         | "value:" name "=" needle     # value de un control (por ejemplo la pantalla de una calculadora)
         | "file:" path                 # recibo independiente: existe el fichero
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
  "procedure": "replayed|learned|none",
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

## 5. Memoria de procedimientos

Ruta: `<data root>/computer-use/procedures.v1.json` (el data root privado del shell,
`MemoryOperationProtector.ResolveDataRoot()`; nunca en el repositorio).

```json
{
  "version": 1,
  "procedures": {
    "steam|ir a la biblioteca": {
      "application": "Steam",
      "goal": "ir a la biblioteca",
      "steps": [
        {"operation": "app.open", "arguments": {"appId": "…"}, "expect": "window"},
        {"operation": "input.visible.click", "arguments": {"label": "Biblioteca"},
         "expect": "control:Biblioteca:selected|surfaceChanged"}
      ],
      "successCheck": "…",
      "learnedUtc": "2026-09-21T03:10:00Z",
      "runs": 3, "replays": 2,
      "lastModelMs": 2400, "lastReplayMs": 900
    }
  }
}
```

- **Clave**: aplicación plegada + objetivo normalizado (plegado, sin envoltura de pedido,
  sin el nombre de la app).
- **Aprende** sólo una misión `reached: true` sin pasos fallidos; guarda la secuencia
  verificada con la expectativa que se observó en cada paso.
- **Reproduce** paso a paso con su verificación; el modelo sólo interviene cuando un paso
  falla o su `expect` no se ve (desvío), y desde ahí sigue el bucle normal. Si la
  reproducción termina con éxito, `replays++`; si se desvió, se sustituye por la secuencia
  nueva si esta llegó.
- **Teclas de activación** (Enter, espacio, Supr) aprendidas no se reproducen ni guardan su
  `target`: ese paso lo decide la mente sobre la vista actual y la reproducción sigue después
  (`ActsOnTheFocusedItem`). Un clic aprendido se fija por identidad al único control de la vista
  con su nombre.
- **Olvida** (v2) un procedimiento que se desvió, o cuyos pasos reproducidos toparon con una pantalla
  que no respondió (dejó de cambiar, sin paso visible, sin evidencia, paso repetido, presupuesto o
  tiempo agotados), uno cuyo propio paso cortó el bucle (sus argumentos ya no encajan, su ventana no es
  la de la app, no se pudo enviar) y uno con argumentos grabados inválidos; lo conserva ante una vista
  no disponible, una ventana tapada o elevada, el modelo sin respuesta o un paso del modelo que no se
  pudo enviar (`ForgetsProcedure`). Al
  abandonar una reproducción la cuenta de vistas sin cambio vuelve a cero: decide la rutina (reintento
  por identidad, BUSCAR) y luego el modelo.
- **Mide** el ahorro: `modelMs` de la primera vez frente a `lastReplayMs`.

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

**Encadenado.** `mission.computer.use` acepta `steps` (1..8 sub-objetivos `{goal, application, successCheck}`) y
`budgetSteps` hasta 30. La mente parte el pedido en cláusulas de hacer («abrí X, andá a Y y escribí Z»), arrastra la
aplicación y la cambia cuando una cláusula nombra otra. El bucle corre los sub-objetivos en orden (≤10 pasos y 30 s
cada uno, ≤30 pasos y 180 s en total), con su propia comprobación, historial y procedimiento; al cambiar de
aplicación olvida el proceso adoptado. El resultado trae `subgoals[]`; el final narra cada parte o la primera que
no se logró.

**BUSCAR (universal, sin modelo, `computer_use._find_step`).** Si el destino no está en la vista: el campo o botón
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

**Página de inicio de un editor** (live v5/v6: Excel y Word abrieron en «Buenos días», con «Libro/Documento en
blanco», los recientes y «Buscar un archivo»; sus pestañas sólo existen con un documento abierto). Un objetivo de
pestaña («ir a / hacer clic en la pestaña X», fuera del navegador) cuya pestaña no está en la vista, en una ventana cuyo
título no nombra un documento (sin segmento « - ») y que ofrece **un** elemento para crear uno vacío (su nombre lleva
en blanco / blank / vacío / empty, ≤ 6 palabras, sin extensión, de un tipo accionable, nunca dentro de una lista de
archivos propios —recientes, anclados, compartidos—; palabras en `semantic/missions.names_a_blank_item`): la persona
crea primero el documento en blanco y después va a la pestaña. Enter sobre la oferta cuando tiene el teclado (la página
se lo da), si no un clic en ella; el paso lleva `code: expects_title_change` y la App vuelve a mirar, sin OCR y hasta
8 s, hasta que cambia el título de la ventana. Crear un documento sin guardar es reversible y no toca ningún archivo;
nunca un reciente, nunca dos veces y nunca cuando el pedido nombra un archivo propio (`names_a_file`: un nombre con
extensión, o archivo/documento/libro/presentación no dichos como nuevos o en blanco). En esos casos, o si la página
sigue tras crear, la mente devuelve `none` con `code: no_document_open` y la misión para con
`computer_use_no_document_open` («la aplicación está en su pantalla de inicio, sin ningún documento abierto»), sin
más clics. Sin oferta (o con dos) no se crea nada.

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
operación tipada elegida por el decisor conserva su ruta (D21). La aplicación es la dicha tras el último «en» («hacé
clic en Ajustes en Steam»), y ese corte sólo enmarca cláusulas de lugar (ir a, hacer clic, seleccionar, activar,
desactivar): «escribí Cuphead en el buscador en Steam» escribe «Cuphead».

**Objetivos libres.** Cuando el decisor elige el motor para un pedido que el lector no sabe partir,
`semantic.missions.free_form_arguments` usa las palabras de la persona tal cual como `goal` (≤ 512 bytes) y, como
`application`, la app instalada que el pedido nombre (si no, la ventana de delante); sin `successCheck`: termina el
`done` del modelo con evidencia en pantalla.

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
vista con captura y OCR en paralelo al árbol y OCR sólo cuando hace falta; 150 ms de asentamiento entre pasos (antes
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
- `input.key.press` e `input.text.type` llevan `window` (el hwnd de la vista sobre la que se decidieron): el provider
  la trae al frente o no envía nada, también al confirmar un paso tras el «sí» con BAXY delante; escribir se para si
  la ventana pierde el frente o se cancela; un texto con salto de línea o tabulador se rechaza. Si la misión nombra
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
  clic en X» cuyo X nombra ese interruptor lo pulsa: es orden de la persona.

**Guardas.**
- Sin clics sobre un control que cubre ≥ 80 % de la ventana (`control_covers_window`); el modelo no repite por
  tercera vez un acto que no hizo aparecer texto nuevo (`no_progress`), y el bucle marca fallido un acto ya hecho
  desde la misma pantalla cuando la pantalla vuelve a ella (`computer_use_no_progress`).
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
  mostrarlo; un valor cortado (120 caracteres) es desconocido. El eco de lo que BAXY escribió (un buscador o su
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
- Una app empaquetada que se dibuja dentro de un marco `ApplicationFrameHost` tiene ese marco por ventana; sus
  ventanas de nivel superior son sus emergentes (medido en vivo: el historial de una búsqueda, «Host de ventanas
  emergentes», se tomó por la app, la vista perdió el campo y se pulsó una entrada del historial). Un control es
  una búsqueda si lo dice su nombre antes de la ayuda que trae («speedtest. Presione la tecla Suprimir…» no lo es), y
  un campo que el recibo del clic dice pulsado conserva el cursor aunque la vista siguiente ya no lo liste: se
  escribe, y el Enter sin un campo de búsqueda visible con el teclado pregunta.
- Una app abierta en frío se vuelve a mirar hasta 10 s mientras la ventana cambie o parezca de arranque (≤ 1 control
  accionable —un marco, un panel o una barra de dirección de sólo lectura no cuentan— y ≤ 5 líneas).
- Una ventana de administrador (`window.elevated`) para la misión con `computer_use_window_elevated`, dicho con esa
  causa.
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
| andá a X / go to X | `ir a X` | `control:X:current\|title:X\|page:X` (+ nombres en el otro idioma); un clic que sólo eligió un elemento de contenido sigue con Enter |
| elegí el lápiz / el color rojo / pick the red color | `seleccionar X` | `control:=X:selected\|control:=X:on\|stepDone:input.visible.click:=X` (+ nombres en el otro idioma) |
| buscá X / search for X | `buscar X` | `title:X&stepDone:input.key.press:enter\|title:X&stepDone:input.visible.click:X\|stepDone:input.text.type&stepDone:input.key.press:enter&text:X` (los resultados en pantalla son la meta) |
| cambiá a científica / pasá a la vista X / switch to X mode | `ir a X` | `control:X:selected\|title:X\|page:X\|header:X` (+ nombres en el otro idioma y el otro género) |
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
`seen.screen`/`seen.evidence`. Las comillas que delimitan un nombre («haz clic en «Sistema»», la reformulación
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
