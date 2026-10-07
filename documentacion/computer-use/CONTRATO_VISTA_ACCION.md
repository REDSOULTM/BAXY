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
      "rect": {"x": 120, "y": 500, "w": 60, "h": 48},   // píxeles de pantalla
      "zone": "BL",                  // rejilla 3×3 sobre la ventana, ver §1.4
      "color": "gray"                // color dominante HSV del rectángulo, ver §1.5
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
  de Win32, no de UIA.
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
| escribir | `input.text.type` | `text` | SendInput aceptado + el control enfocado no es `password` |
| tecla | `input.key.press` | `key` (enum cerrado, ahora con combos `ctrl_a ctrl_c ctrl_f ctrl_k ctrl_t ctrl_w ctrl_z f5`), `target?` (`message_composer`) | SendInput aceptado |
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
| clic cuyo `label` es **enviar** (`enviar`, `send`) o `enter` con `target: message_composer` | **confirma** | llega a una persona (misma regla que `message.send`) |
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
   contiene X (el tipo de control nombrado en el objetivo acota la búsqueda). Un paso que acaba de fallar nunca se repite: lo que sigue lo decide el
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
         | "control:" name [ ":" state ]   # control con ese nombre (plegado) y, si se da, ese estado (selected|on|off|expanded|focused)
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
operación (y ese `key`/`label`) está en la misión.

### 4.4 Protocolo mente ↔ shell: `computer.use.step`

Petición del shell (JSONL, mismo canal que `plan.ground`):

```json
{
  "type": "computer.use.step",
  "objective": "abre Steam y ve a la biblioteca",   // lo que dijo la persona
  "goal": "ir a la biblioteca",
  "application": "Steam",
  "successCheck": "…",
  "view": { …§1.2, sin surface/elapsedMs/rect… },
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

**BUSCAR (universal, sin modelo).** Si el destino no está en la vista: el campo o botón de búsqueda visible (léxico
bilingüe) → escribir el destino → clic en el resultado que lo nombra (nunca Enter: un canal de voz sigue siendo un
clic que `RiskPolicy` confirma); si no hay, `ctrl_k` y `ctrl_f` (sólo si aparece un campo con foco; si no, Escape);
después desplazar la lista más poblada (`input.scroll {index}`); sólo entonces el modelo. Un menú abierto por el clic
en el destino elige la entrada que nombra el objetivo.

**Último recurso.** Una orden sobre el PC que el turno cerró como límite pasa al motor con las palabras de la persona
como objetivo (`semantic.missions.engine_can_try`), salvo preguntas, lugares fuera del PC, prohibiciones y objetivos
de borrar, formatear, desinstalar, comprar o pagar.

**Velocidad.** Paso del modelo con gramática GBNF de acto primero (`{"act":"click","i":12}`, ~10 tokens: 0,2–0,7 s);
30 controles ordenados por el objetivo con la nota «N de M»; teclas y texto en proceso (SendInput, ~50 ms); clic sin
esperas fijas (estado UIA cada 50 ms y superficie desde 150 ms); vista con captura y OCR en paralelo y OCR sólo cuando
hace falta; espera de 150 ms entre pasos; apertura de apps UWP por su marco (antes 30 s); worker precalentado al
arrancar el core; sin etiquetas de progreso escritas por el LLM durante una misión.

**Guardas.** Sin clics sobre controles que cubren ≥80 % de la ventana; sin repetir un acto que no hizo progresar;
`page:` sólo cuenta un clic sobre el destino o la entrada de menú que abrió, contra la primera vista de la propia
app; una app recién lanzada se espera hasta que deja su ventana de arranque; una ventana de administrador
(`window.elevated`) para la misión con esa causa; `RiskPolicy` confirma también publicar, responder, comentar,
compartir, unirse, comprar, pagar, borrar y desinstalar.

**Lectura del pedido v2 (`semantic/missions.py`).** Cada cláusula de hacer trae su comprobación determinista; una
cadena con una cláusula sin comprobación sigue siendo del decisor. Familias y comprobación:

| Cláusula | Objetivo | `successCheck` |
|---|---|---|
| creá una carpeta llamada X / create a folder named X | `crear carpeta X` | `control:X` |
| renombrá A a B / rename A to B | `renombrar A a B` | `control:B` |
| elegí el lápiz / el color rojo / pick the red color | `seleccionar X` | `control:X:selected\|control:X:on\|stepDone:input.visible.click:X` (+ nombres en el otro idioma) |
| buscá X / search for X | `buscar X` | `title:X\|stepDone:input.text.type&stepDone:input.key.press:enter&text:X` |
| poné la primera / play the first one / ponelo | `reproducir …` | `control:pausa&stepDone:input.visible.click` (y `pause`, y con tecla) |
| copiá / pegá / deshacé / seleccioná todo | `apretar ctrl c` … | la tecla o el clic en su control |
| abrí una pestaña nueva | `apretar ctrl t` | `stepDone:input.key.press:ctrl_t` |
| andá a es.wikipedia.org | `ir a la direccion …` (ctrl_l, texto, Enter) | `title:wikipedia` |
| abrí la sección Historia | `ir a historia` | lo de `ir a` + el clic verificado en la sección |
| calculá 12 por 7 / multiply 6 by 7 | `calcular 12 × 7` | la de calcular |

En una cadena el verbo puede decirse una vez («elegí el lápiz y después el color rojo», «go to System, then
Display», «hacé clic en Insertar y después en Tabla»), un pronombre o un lugar genérico retoma lo último nombrado
(«buscá Hades y abrilo», «creá la carpeta X y entrá», «buscá a Mamá y abrí el chat»), una cláusula que nombra otra
aplicación cambia la del paso («… y pegalo en el Bloc de notas») y una pregunta final («… y decime si el modo es
claro u oscuro») no es sub-objetivo: va al final del `goal` tras `; y responder: ` y el final la contesta sólo con
`seen.screen`/`seen.evidence`. Nunca es misión un pedido que ordena borrar, vaciar, formatear, desinstalar, comprar
o pagar (lo tecleado no cuenta). Tipado contra motor: en una cadena sólo las operaciones tipadas que no son
primitivas del motor cubren sub-objetivos; un cálculo dicho dentro de una aplicación se hace en ella.

El paso de tecleo guarda en qué campo se escribió (`into`); el átomo `control:` descarta lo tecleado sólo si se
tecleó en una búsqueda, una barra de direcciones o un campo sin nombre (el eco de sus sugerencias), no el nombre
escrito en la caja de un elemento que se crea o se renombra. Corpus: `tests/test_computer_use_corpus.py`.
