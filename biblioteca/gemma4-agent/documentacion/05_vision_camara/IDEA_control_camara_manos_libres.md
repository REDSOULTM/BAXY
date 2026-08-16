# Control manos-libres por cámara (mirada + gestos) — complemento de Gemma 4

> **Estado:** diseño / idea (sin código todavía). Documento de visión para decidir
> el build con presupuesto y gates, antes de gastar recursos (CLAUDE.md #1, #3).
> **Fecha:** 2026-05-31.

---

## 0. Resumen ejecutivo

Un segundo canal de control del PC, **sin manos en el teclado/mouse**, por **cámara web**:
la **cabeza/mirada** dice *dónde* y los **gestos de mano** dicen *qué hacer*. Complementa
al control por **voz** que ya existe (la voz dice intenciones complejas; la cámara hace
manipulación directa: apuntar, clickear, arrastrar, cerrar).

**El reparto honesto, medido contra el estado del arte:**

| Capacidad | Veredicto | Por qué |
|---|---|---|
| **Gestos de mano** (puño, pinza, palma, apuntar) | ✅ **Sólido** | MediaPipe Hands corre 30fps en **CPU**, ~99% de acierto en gestos, Apache-2.0 |
| **Pose de cabeza** → región del monitor | ✅ **Viable** | Estable (es lo que usan eViacam/Camera Mouse para accesibilidad) |
| **Mirada (iris)** → cursor **preciso** | ⚠️ **Techo físico** | Webcam común: error de decenas de px + jitter → no apunta fino solo con ojos |
| **Precisión real al clickear** | ✅ **Resuelta** | **Snap-to-elemento**: la región gruesa → la cascada UIA/OCR (ya existe) ancla el cursor al botón/pestaña más cercano |

**Idea central:** no peleamos contra el techo de la mirada. La cabeza/mirada da el *dónde
aproximado*, **la cascada UIA/OCR de Gemma 4 da la precisión** (snap al elemento), y el gesto
da la acción. Por eso es un **complemento perfecto**: reusa lo que ya construimos.

---

## ⚙️ PRINCIPIO RECTOR (lo más importante): 100% determinista — el LLM SOLO bajo pedido

**Esta fase es un sistema de control DETERMINISTA, DESCONECTADO del LLM.** Gemma 4 (el 4B)
**NO participa** del control por mirada/gestos. Mover el cursor y clickear es **geometría +
máquina de estados**, no inferencia. No es negociable: el control debe ser **real-time,
predecible y privado**. El LLM se enciende **solo cuando vos lo pedís explícito** y la tarea
necesita *entender* (no solo *detectar*).

### Las 3 capas y dónde (no) entra el LLM

| Capa | Qué hace | ¿LLM? | Latencia |
|---|---|---|---|
| **L1 — Control** | mirada/cabeza → cursor; gesto → click/cerrar/arrastre/scroll | **NO** — geometría + state-machine | tiempo real (~33ms) |
| **L2 — Eventos de cámara** | "entró una persona", "se fue", wake, movimiento | **NO** — detección geométrica (aparece/desaparece una cara) | tiempo real |
| **L3 — Semántica** | entender / describir contenido | **SÍ, pero SOLO bajo pedido explícito** | bajo demanda |

### El LLM entra SOLO acá (tus ejemplos)
- *"¿Qué ves en mi pantalla?"* → **L3**: `vision.describe_screen` lee la pantalla con el LLM.
  Es un **pedido puntual por voz**, NO parte del control. El LLM mira una vez y responde.
- *"Avisame cuando entre alguien a mi pieza"* → se **configura** por voz (el LLM parsea el
  pedido **una sola vez** y arma un *watcher*), pero la **vigilancia corre en L2 determinista**:
  la cámara cuenta caras/personas en cuadro → aparece una nueva → dispara la notificación.
  **El LLM NO mira cada frame.** Solo arma el watcher y, si lo pedís, describe quién (L3 opcional).

### Por qué esta separación es obligatoria
- **Latencia:** el cursor no puede esperar un round-trip al LLM (segundos). L1/L2 son ~33ms.
- **Privacidad:** el LLM/visión **no está mirando siempre** — solo cuando lo pedís. La cámara
  procesa landmarks geométricos en memoria y los **descarta**; nada se interpreta ni guarda
  salvo pedido explícito. Indicador visible de "cámara activa".
- **Fiabilidad:** un control determinista **no puede alucinar** un click. La geometría del
  gesto es la geometría — no hay un modelo decidiendo si clickear.
- **Recursos:** L1/L2 en **CPU, 0 VRAM**. El LLM (que sí usa los 6GB del 4B) se invoca **solo
  puntual**, no en loop.

### Tareas de monitoreo: el watcher elige el camino más barato (L2 antes que L3)
"Avisame cuando **[condición]**" → el agente traduce **una vez** la condición a un watcher:
- *"cuando entre alguien"* → **L2 determinista**: nº de caras sube → notificar.
- *"cuando me vaya / no esté"* → sin cara por N s → bloquear/pausar.
- *"cuando alguien mire mi pantalla"* → 2ª cara orientada a la pantalla → avisar (privacy).
- *"avisame si mi gato sube al escritorio"* → condición **semántica** → ahí sí visión-LLM
  periódica (más caro, **opt-in con presupuesto explícito**). Solo si no hay forma geométrica.

> **Regla:** todo lo que se pueda resolver con geometría (L1/L2) **NUNCA** toca el LLM. El LLM
> es el último recurso, bajo pedido, con su presupuesto. El control es tuyo y de la cámara, no
> del modelo.

---

## 1. Visión y filosofía

- **Accesibilidad primero.** Alguien que no puede usar mouse/teclado controla el PC con
  cabeza + manos (o solo cabeza, por *dwell*, si tampoco puede gesticular).
- **Complemento, no reemplazo.** Convive con la voz: decís *"abrí Discord"* (voz) y después
  *mirás un canal + hacés pinza* (cámara). Cada canal hace lo que mejor le sale.
- **Determinista y local.** El mapeo gesto→acción es **estructural** (no IA que adivina la
  intención — CLAUDE.md (b)). Todo on-device, **0 nube**, **0 VRAM extra** (corre en CPU).
- **Sin sorpresas.** "Dead-man switch": el control solo actúa cuando la mano está en la zona
  de control / tras un gesto de activación. Bajás la mano → se desactiva. Nada de clicks
  fantasma.

---

## 2. Cómo complementa al control por voz

| Eje | Voz (ya existe) | Cámara (esta idea) |
|---|---|---|
| Fuerte en | Intenciones complejas, multi-paso, búsqueda, dictado | Apuntar, clickear, arrastrar, cerrar, scroll |
| Débil en | Apuntar a "esa pestaña de ahí" sin nombrarla | Comandos abstractos / texto largo |
| Comparten | **La cascada UIA→OCR→visión** (encontrar el elemento clickeable) | idem |
| Ejemplo | "mandale a Letras que ya voy" | mirar la X de una pestaña + puño = cerrar |

**Sinergia:** ambos resuelven "¿qué elemento de la pantalla?" con el **mismo motor**
(UIA/OCR). La voz lo resuelve por *nombre* ("el botón Guardar"); la cámara por *posición*
(donde apunta la cabeza) + snap. Un solo cerebro de grounding, dos formas de apuntar.

---

## 3. Arquitectura general

```
            ┌─────────────── CÁMARA (30fps, CPU) ───────────────┐
            │                                                    │
   ┌────────▼────────┐   ┌──────────────────┐   ┌───────────────▼────────┐
   │ MediaPipe Face  │   │ MediaPipe Hands  │   │  (opcional) Iris/gaze  │
   │ Mesh (cabeza)   │   │ (21 landmarks)   │   │   refinamiento fino    │
   └────────┬────────┘   └────────┬─────────┘   └───────────┬────────────┘
            │ yaw/pitch/roll       │ gesto + posición        │ dirección ojos
   ┌────────▼──────────────────────▼─────────────────────────▼────────────┐
   │  FUSIÓN + SUAVIZADO (one-euro/Kalman) + CALIBRACIÓN por-usuario       │
   │  -> (x,y) en el LIENZO VIRTUAL (unión de los N monitores) + gesto     │
   └────────┬──────────────────────────────────────────┬──────────────────┘
            │ región gruesa (x,y) + monitor             │ gesto reconocido
   ┌────────▼────────────────────────┐        ┌─────────▼──────────────────┐
   │ SNAP-TO-ELEMENTO                │        │ MÁQUINA DE ESTADOS de gesto │
   │ (cascada UIA/OCR de Gemma 4)    │        │ (determinista, dead-man)    │
   │ -> ancla el cursor al elemento  │        │ -> acción (click/cerrar/…)  │
   └────────┬────────────────────────┘        └─────────┬──────────────────┘
            └───────────────► EJECUTOR (gui.click / keypress / drag) ◄──────┘
                                  (con verificación, como ya hace el agente)
```

- **MediaPipe Face Mesh:** 468 puntos → pose de cabeza (yaw/pitch/roll) + posición de iris.
- **MediaPipe Hands:** 21 landmarks por mano → gesto (ángulos de dedos) + posición.
- **Fusión:** cabeza = puntero grueso; iris = refinamiento opcional; gesto = acción.
- **Snap-to-elemento:** la pieza que reusa **todo lo que ya construimos** esta sesión.

---

## 4. Las 3 capas del puntero (de grueso a fino)

1. **Cabeza (primaria).** Hacia dónde apunta tu cara → región. Más estable que iris puro;
   naturalmente girás la cabeza hacia lo que mirás. Es el approach probado de accesibilidad
   (Camera Mouse, eViacam).
2. **Iris/mirada (refinamiento, opcional).** Ajusta dentro de la región de la cabeza. Aporta
   el "feeling" de *donde miro*, pero **no se confía para precisión** (jitter).
3. **Snap-to-elemento (precisión).** La región gruesa entra a la **cascada UIA→OCR**: se
   listan los elementos clickeables cercanos (pestaña, botón, link) y el cursor invisible
   **salta al más cercano** a la mirada. Acá nace la precisión que la cámara no da sola.

> **Mouse invisible:** por defecto el cursor está oculto/sutil y sigue la mirada sin molestar.
> Cuando la mano entra a la zona de control, el cursor se "arma" (snap al elemento + listo
> para clickear). Así la mirada no mueve un cursor visible distrayendo todo el tiempo.

---

## 5. Multi-monitor (el corazón de tu setup: 3 monitores)

El desafío real con 2-3 monitores: mapear la dirección de cabeza/mirada a una coordenada
sobre un **lienzo virtual ancho** (la unión de los monitores).

### 5.1 Detección del layout
Por OS (`EnumDisplayMonitors` de win32): lista de monitores con su **rect en el escritorio
virtual**, resolución y posición. Se arma el lienzo virtual:

```
  Monitor IZQ        Monitor CENTRO         Monitor DER
 (-1920,0)→(0,1080) (0,0)→(1920,1080)   (1920,0)→(3840,1080)
 [    ◐ izq    ]    [     ▲ centro    ]   [    ◑ der    ]
        \                  |                    /
         \                 |                   /
          ╲________  cabeza/cara  ________╱
                      (webcam)
```

### 5.2 Selección de monitor por **yaw** (giro horizontal de cabeza)
- Yaw fuertemente a la izquierda → monitor IZQ.
- Yaw centrado → monitor CENTRO.
- Yaw a la derecha → monitor DER.
- (Con 3 monitores el rango de yaw es ~±30-45°, cómodo de discriminar.)

Una vez elegido el monitor, **pitch (arriba/abajo) + yaw fino** ubican la región dentro de él.

### 5.3 Calibración (clave para que ande)
El user mira/apunta a puntos conocidos: las **4 esquinas + centro de cada monitor**
(3 monitores ≈ 9-15 puntos, con interpolación se puede menos). Se entrena una **regresión**
(features de cabeza+iris → coordenada virtual). Resultado: un mapeo personalizado.
- Dura ~30-60s, una vez por layout.
- Se **persiste local** (como los perfiles de `~/.gemma4/`), por **usuario** y por **layout**.
- Re-calibración rápida si cambiás de silla/luz (un "vuelvo a centrar" con 3 puntos).

### 5.4 Suavizado anti-jitter
Filtro **one-euro** o Kalman sobre el puntero (la cámara tiembla; sin filtro el cursor
vibra). Más *snap-to-elemento* que perdona el resto.

---

## 6. Multi-usuario y layouts variables (3 / 2 / 1 monitores)

- **Perfiles de calibración por usuario** (`~/.gemma4/camera/<user>/calib_<layout-hash>.json`).
  El layout se hashea (cantidad+resolución+posición de monitores) → cada combo tiene su
  calibración. Cambiás de PC/monitores → se detecta el nuevo layout → pide calibrar (o usa
  una calibración base genérica degradada).
- **1 monitor:** trivial (el yaw cubre un solo lienzo). **2 monitores:** yaw izq/der. **3+:**
  yaw en 3+ zonas. El diseño escala con N (no hay número mágico hardcodeado).
- **Sin calibración:** modo degradado usable solo con *dwell* + snap (menos preciso, pero
  arranca). La calibración lo vuelve fino.

---

## 7. Vocabulario de gestos (determinista) + activación

> **Regla de oro (anti-accidente):** el control de gestos SOLO actúa cuando hay una mano en
> la **zona de control** (o tras el gesto de *wake*). Bajás la mano = desactivado. Las
> acciones **destructivas** (cerrar, borrar) piden un 2º gesto o *dwell* de confirmación.

| Gesto / seña | Acción | Notas |
|---|---|---|
| **Mano entra a la zona** | *Arma* el puntero (snap + listo) | dead-man on |
| **Pinza** (pulgar+índice se tocan) | **Click izquierdo** preciso | el gesto más fino |
| **Pinza doble / mantener** | Doble-click / click derecho | configurable |
| **Puño** (cerrar mano) | **Agarrar** el elemento bajo el cursor | tu ejemplo: sobre la X = cerrar pestaña; sobre la barra de título = modo **arrastre** |
| **Puño + mover mano** | **Arrastrar** (la pestaña/ventana sigue la mano) | "controlar la pestaña" |
| **Abrir la mano** (soltar el puño) | **Soltar** (fin del arrastre / drop) | |
| **Palma abierta empujando** | **Escape / cancelar** | |
| **2 dedos (índice+medio) ↑/↓** | **Scroll** | velocidad por amplitud |
| **Índice apunta + *dwell*** (quieto N ms) | **Click por permanencia** | para quien no puede gesticular |
| **Pulgar arriba** | **Confirmar** (sí) | confirmaciones |
| **Gesto de *wake*** (ej. "L" pulgar+índice, o mano abierta 1s) | **Activar/desactivar** todo el modo cámara | toggle global |

**Cara/ojos como señas (complemento):**
- **Parpadeo intencional largo / doble parpadeo** → click alternativo (para manos ocupadas).
- **Cejas arriba / boca abierta** (MediaPipe blendshapes) → confirmaciones secundarias.
- **Mirada sostenida (*gaze dwell*)** → pre-selección del elemento (se ilumina antes de clickear).

Tu ejemplo literal —*"miro una pestaña, hago puño, se cierra; al hacer puño controlo la
pestaña"*— se mapea exacto:
```
mirada → región (pestaña)  →  snap a la pestaña  →  PUÑO = agarrar
   → si la mano se mueve: arrastra la pestaña    →  ABRIR MANO = soltar
   → si el puño cae sobre la X (snap): cierra (con confirmación si está activada)
```

---

## 8. Snap-to-elemento (reuso de lo que ya construimos)

La pieza que hace todo viable, y que **ya existe en Gemma 4** (esta sesión):
- **UIA** (apps nativas) lista controles clickeables con sus rects.
- **OCR (Tesseract, fix de palabra+región de hoy)** para texto/UI web cuando UIA falla.
- La región de la mirada → se consultan los elementos cercanos → el cursor **salta al más
  cercano** a la mirada (ponderado por distancia + tipo de elemento).
- El gesto ejecuta sobre **ese elemento verificado** (no sobre un píxel a ciegas) → usa el
  mismo `gui.click_button` con verificación antes/después que ya tiene el agente.

> Sin snap, la cámara erra la pestaña. Con snap, la cámara solo tiene que apuntar *cerca* —
> el grounding hace el resto. **Esa es la ventaja de hacerlo complementario al agente.**

---

## 9. Determinismo, seguridad y privacidad

- **Determinista:** gesto→acción es una **máquina de estados** explícita (no un modelo que
  adivina). Cumple CLAUDE.md (b): nada de listas/IA para decidir la acción; la FORMA del
  gesto (ángulos de dedos) la decide.
- **Dead-man + confirmaciones:** sin mano en zona = sin acciones. Destructivo = 2º gesto/dwell.
- **Privacidad:** **todo on-device**, sin nube. El video **no se graba ni se sube**; se
  procesan landmarks en memoria y se descartan. Indicador visible de "cámara activa".
- **Apagado total:** un gesto de wake o un comando de voz ("apagá el control por cámara")
  desactiva todo. Master switch en Settings.

---

## 10. Restricciones técnicas (chequeo)

| Restricción del producto | ¿Cumple? | Detalle |
|---|---|---|
| **Licencia de uso COMERCIAL** (se va a VENDER) | ✅ | MediaPipe **Apache-2.0**, OpenCV **Apache-2.0**, filtro one-euro (BSD/MIT). **PROHIBIDO GPL/AGPL/non-commercial** (por eso se descartó OmniParser=YOLOv8 AGPL). |
| 6 GB VRAM (el 4B la usa) | ✅ | MediaPipe corre en **CPU** → **0 VRAM extra** |
| CPU para STT (Whisper) | ✅ convivencia | MediaPipe Hands ~1 core; Face Mesh ~1 core; Whisper solo en turnos de voz |
| Latencia tier-Alexa | ✅ | 30fps = ~33ms/frame; el snap/click es instantáneo |
| Local/privado | ✅ | on-device, sin nube |
| Multi-usuario/universal | ✅ | calibración por usuario+layout; sin optimizar sobre una sola cara |

**Costo de cómputo honesto:** 2 pipelines de MediaPipe + el filtro corren continuos en CPU.
En laptop modesto puede ser ~10-20% de CPU sostenido. Mitigación: bajar el FPS de la cara a
~15 (la cabeza no necesita 30), correr Hands solo cuando hay mano en cuadro, y un perfil
"cámara off" para máquinas justas.

### Licencia para VENDER (regla dura, verificada con fuentes)

El programa se va a **vender** → **cada dependencia (código Y modelos) debe permitir uso
comercial**. Verificado:

| Componente | Licencia | ¿Vendible? |
|---|---|---|
| **Gemma 4** (modelo core) | **Apache 2.0** (desde 2026; antes "Gemma Terms" restrictivo) | ✅ vendés acceso/fine-tune sin acuerdo con Google |
| MediaPipe (manos/cara) | Apache 2.0 | ✅ |
| OpenCV | Apache 2.0 | ✅ |
| Tesseract (OCR) | Apache 2.0 | ✅ |
| Whisper (STT) | MIT | ✅ |
| Piper (TTS) | MIT (pero chequear licencia de **cada voz**) | ✅* |
| llama.cpp | MIT | ✅ |
| sentence-transformers | Apache 2.0 | ✅ |
| ~~OmniParser / YOLOv8~~ | ~~AGPL-3.0~~ | ❌ **DESCARTADO** (copyleft = veneno comercial) |

**Reglas duras del producto vendible:**
1. **NUNCA** una dep **GPL/AGPL/non-commercial/research-only**. Antes de agregar **cualquier
   librería o modelo**, verificar la licencia (Apache/MIT/BSD/CC0 = OK).
2. **Los modelos y datasets también tienen licencia** (no solo el código): voces de TTS,
   wake-words, encoders. Chequear cada uno — algunas voces Piper o datasets son no-comercial.
3. **Auditoría antes de lanzar:** correr `pip-licenses` (o similar) sobre todo el árbol de
   deps + revisar `models/`. Dejar un `THIRD_PARTY_LICENSES.md` en el instalador.
4. **Atribución obligatoria:** Apache/MIT exigen incluir el aviso de copyright + el texto de
   licencia de cada dep. Generarlo automáticamente.
5. Gemma 4 (Apache 2.0) ya no arrastra los "Gemma Terms" viejos — pero respetá igual la
   política de uso prohibido (nada ilegal/dañino) por buena práctica.

> **Gran noticia:** el stack core (Gemma 4 + MediaPipe + OpenCV + Whisper + Piper + llama.cpp +
> Tesseract) es **TODO permisivo (Apache/MIT/BSD)** → el producto **es vendible**. Solo resta la
> auditoría formal antes de lanzar y la disciplina de **"jamás AGPL/GPL"** al sumar deps/modelos.
> Fuentes: [MediaPipe comercial](https://quickpose.ai/faqs/can-mediapipe-be-used-commercially/) ·
> [Gemma 4 Apache 2.0](https://www.mindstudio.ai/blog/gemma-4-apache-2-license-commercial-ai-deployment).

---

## 11. Roadmap por fases + gates medibles

> Cada fase tiene un **gate** (número contra criterio) antes de seguir — CLAUDE.md #3.

| Fase | Qué | Gate (medido en TU hardware) |
|---|---|---|
| **0. POC** | Prender cámara, MediaPipe Hands+Face, overlay de gesto+región | ≥20 fps sostenido; gesto puño/pinza/abierto detectado ≥95% |
| **1. Gestos→acción** | Máquina de estados + dead-man; click/scroll por gesto (cursor normal) | 0 clicks fantasma en 10 min de uso normal; pinza→click ≥95% |
| **2. Puntero cabeza** | Pose de cabeza → cursor; suavizado one-euro | cursor estable (jitter < X px); cubre 1 monitor |
| **3. Calibración + multi-monitor** | Calibrar 4 esquinas/monitor; yaw→monitor; lienzo virtual | acierta el monitor correcto ≥98%; región dentro de ±150px |
| **4. Snap-to-elemento** | Conectar a la cascada UIA/OCR; cursor invisible se ancla | click aterriza en el elemento correcto ≥90% (como el OCR-click de hoy) |
| **5. Gestos ricos** | Arrastre (puño+mover), cerrar pestaña, confirmaciones, ojos | tu caso "miro pestaña + puño = cerrar" en vivo, sin error |
| **6. Integración Gemma 4** | Perfil `camera_enabled`, modo togglable por voz, Settings | convive con voz; on/off limpio; perfiles por usuario persistidos |

**Experimento mínimo primero (Fase 0):** instalar MediaPipe+OpenCV (~150MB CPU), correr el
POC, **medir FPS + fiabilidad de gesto + estabilidad de cabeza en TU PC con 3 monitores**.
Si el gate pasa → seguimos; si no → ajustamos (o paramos honesto).

---

## 12. Techos honestos (lo que NO va a ser perfecto)

- **Mirada precisa sola:** no. Por eso head-pose + snap. Si esperás "el cursor exacto donde
  miro al píxel" solo con los ojos y una webcam → no se puede (físico). Con snap, no importa.
- **Luz / cámara mala:** el tracking se degrada con poca luz o webcam berreta. Mitigación:
  indicador de calidad + pedir más luz; head-pose aguanta mejor que iris.
- **Lentes / gorra / barba:** MediaPipe aguanta bastante, pero casos extremos bajan precisión.
- **Fatiga:** mantener gestos cansa; por eso *dwell* + gestos cortos + la voz para lo pesado.
- **Calibración por layout:** cambiar de monitores pide recalibrar (rápido, pero existe).
- **No es un mouse gamer:** para apuntado fino y rápido (FPS games, diseño de píxel) la
  cámara no compite con un mouse. Es para **navegar, clickear, controlar** — accesibilidad y
  productividad, no precisión sub-píxel.

---

## 13. Integración con Gemma 4

- **Perfil:** `camera_enabled` (ya reservado en `infra/profiles.py`) enciende el subsistema.
- **Subsistema nuevo:** `gemma4_agent/vision_input/` (cámara + MediaPipe + calibración +
  máquina de gestos), aislado del core, opt-in.
- **Reuso:** el snap llama a la **misma cascada** (`computer_use_caps` / `gui` tools) que la
  voz — un solo grounding.
- **Modos:** togglable por **voz** ("activá el control por cámara"), por **gesto de wake**, y
  por Settings. Convive con voz simultánea (voz para comandos, cámara para apuntar/clickear).
- **Sin tocar el runtime pesado:** MediaPipe en CPU, en su propio hilo/proceso; no compite por
  la VRAM del 4B.

---

## 14. Fuentes

- MediaPipe Hands — tracking de mano on-device en tiempo real:
  https://arxiv.org/pdf/2006.10214 · https://research.google/blog/on-device-real-time-hand-tracking-with-mediapipe/
- Reconocimiento de gestos on-device en tiempo real (puño/OK/etc., 30fps):
  https://arxiv.org/pdf/2111.00038
- MediaPipe Holistic (cara+manos+pose simultáneo, on-device):
  https://research.google/blog/mediapipe-holistic-simultaneous-face-hand-and-pose-prediction-on-device/
- Accesibilidad por pose de cabeza (referencia de approach): Camera Mouse, eViacam (head-mouse).

---

## 15. Detalle de implementación (para construir)

### 15.1 Estructura del módulo (nuevo, aislado, opt-in)
```
gemma4_agent/vision_input/
  __init__.py
  camera.py          # captura (OpenCV VideoCapture) + loop a ~30fps, hilo propio
  landmarks.py       # MediaPipe Face Mesh + Hands -> features (yaw/pitch/roll, dedos)
  gestures.py        # geometría de landmarks -> gesto (puño/pinza/palma/apuntar) + state machine
  pointer.py         # fusión cabeza(+iris) -> (x,y) virtual; filtro one-euro
  calibration.py     # calibrar por usuario+layout; persistir ~/.gemma4/camera/
  monitors.py        # EnumDisplayMonitors -> lienzo virtual; yaw->monitor
  snap.py            # (x,y) -> elemento clickeable (REUSA UIA/OCR del proyecto)
  controller.py      # orquesta: pointer + gesture -> acción (REUSA gui tools)
  watchers.py        # L2: eventos de cámara (persona entra, etc.) deterministas
```
Todo **CPU**, hilo/proceso aparte, **sin tocar** el runtime del 4B. Gate por
`profiles.camera_enabled`.

### 15.2 Máquina de estados del control (determinista)
```
   IDLE  ──(mano entra a zona / wake)──►  ARMED
   ARMED ──(cabeza/iris)──► mueve cursor invisible + SNAP a elemento
   ARMED ──(pinza)──► CLICK en el elemento snapeado
   ARMED ──(puño)──► GRAB: si pestaña=cerrar; si ventana=DRAGGING
   DRAGGING ──(mano se mueve)──► arrastra; ──(abrir mano)──► DROP -> ARMED
   ARMED ──(2 dedos ↑/↓)──► SCROLL
   ARMED ──(mano sale / wake)──► IDLE   (dead-man: sin acciones)
   *destructivo (cerrar/borrar)*: exige 2º gesto o dwell de confirmación
```

### 15.3 Flujo de calibración (UX, ~45s, 1 vez por usuario+layout)
1. Detecta el layout (monitores) → arma el lienzo virtual.
2. Aparece un punto en cada esquina+centro de cada monitor, uno por uno.
3. El user **mira/apunta la cabeza** al punto + confirma (gesto/dwell/voz).
4. Se entrena la regresión (features cabeza+iris → coord virtual). RMS error reportado.
5. Persiste `~/.gemma4/camera/<user>/calib_<layout-hash>.json`. Re-centrar rápido = 3 puntos.

### 15.4 Reconocimiento de gestos (geometría, sin ML extra)
Con los 21 landmarks de la mano: ángulos de cada dedo (flexionado/extendido) +
distancias (pulgar↔índice). Reglas:
- **Puño:** los 4 dedos flexionados + pulgar cerrado.
- **Pinza:** distancia pulgar↔índice < umbral, resto extendido.
- **Palma:** 5 dedos extendidos.
- **Apuntar:** índice extendido, resto flexionado.
- **2 dedos:** índice+medio extendidos.
Umbrales calibrables por usuario; histéresis para no titilar entre gestos.

---

## 16. Qué REUSAR del proyecto (NO armar de 0)

> El control por cámara **no reimplementa** clicks, grounding ni visión: **reusa las tools que
> ya existen** en Gemma 4. La cámara solo aporta *dónde apuntar* y *qué gesto*; el resto ya está.

| Necesidad de la cámara | REUSAR de Gemma 4 (ya construido) |
|---|---|
| **Click físico** en (x,y) | `self.tools.execute("gui", {"action":"click", "x":.., "y":..})` |
| **Click por elemento/label** (snap) | `self.tools.execute("gui", {"action":"click_button", "label":X, "window":W})` — corre la **cascada UIA→OCR→visión** con verificación |
| **Snap-to-elemento** en (x,y) | `uiautomation.ControlFromPoint(x,y)` (validado esta sesión) + `ops_tools.ocr_find_text` (fix de palabra+psm11) para texto/web |
| **Keypress / combos** (ctrl+w cerrar) | `self.tools.execute("gui", {"action":"keypress", "keys":"ctrl+w"})` |
| **Scroll** | `self.tools.execute("gui", {"action":"scroll", ...})` |
| **Listar ventanas / títulos** | `self.tools.list_windows()` / `win32gui.EnumWindows` |
| **Monitores / geometría** | `win32api.EnumDisplayMonitors` (igual que ya se usa para rects) |
| **L3 "qué ves en mi pantalla"** | `self.tools.execute("vision", {"action":"describe_screen", "target":...})` |
| **L3 configurar watcher por voz** | el pipeline de voz existente (`run_content`) parsea "avisame cuando…" |
| **Notificar / TTS** | la tool de voz/TTS existente (decir la alerta) |
| **Perfil on/off, persistencia** | `infra/profiles.py` (`camera_enabled`) + el patrón de `~/.gemma4/` |
| **Verificación antes/después** | `computer_use_pkg/gui_verify.py` (ya verifica que el click tuvo efecto) |

**Lo ÚNICO nuevo a construir:** captura de cámara + MediaPipe (landmarks) + calibración +
fusión a (x,y) + la máquina de estados de gestos. **El brazo ejecutor y el grounding YA
existen** — la cámara los llama.

**Caveat comercial (de la auditoría):** si el producto se vende, resolver `piper-tts` (GPL,
linkeado en `voice/tts.py`) — subprocess o reemplazo Apache/MIT. Ver `AUDITORIA_licencias.md`.

---

## Próximo paso

**Fase 0 (POC):** prender la cámara + MediaPipe, medir FPS y fiabilidad de gesto/cabeza en tu
PC de 3 monitores. Es un experimento chico (~150MB de deps CPU) que valida el piso ANTES de
construir el sistema completo. Si el gate pasa, avanzamos fase por fase con los gates de
arriba. La parte de **gestos es sólida**; la de **mirada la resolvemos con head-pose +
snap-to-elemento reusando la cascada que ya construimos**.
