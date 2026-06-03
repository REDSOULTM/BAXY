# Fase 1 - Control fijo de ventanas por mirada + gestos

Estado: implementado como POC aislado en `gemma4_agent/vision_input/window_control.py`.

## Principio

La mirada/cabeza elige la ventana. La mano elige la accion.

No usa LLM, no analiza video semanticamente y no guarda frames. La ventana mirada se resuelve
con Win32 (`WindowFromPoint` + top-level window) usando el punto de cabeza filtrado que ya paso
Fase 0.

El puntero ahora fusiona **cabeza + iris** por defecto: la cabeza elige monitor/region y los
landmarks de iris refinan el punto dentro de esa region. El overlay muestra `src head+iris`
cuando el refino esta activo y hay landmarks de iris suficientes.

Tambien aplica **auto-centrado adaptativo** por defecto para tolerar mejor posicion fisica de
camara (arriba, lateral o con angulo), corrigiendo sesgo constante de cabeza/iris sin agregar
nuevas acciones.

## Modo seguro

Por defecto el runner NO mueve ventanas. Solo muestra overlay con:

- camara activa
- ventana candidata bajo la mirada
- ventana armada despues de dwell corto
- gesto detectado
- accion que se ejecutaria
- cursor de mirada estimado (`gaze`) en la vista de camara
- mini-mapa del escritorio virtual con punto de mirada y ventana candidata/armada

Comando:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models
```

Salir:

```text
q o Esc
```

## Ejecutar acciones reales

Cuando el overlay apunte bien a la ventana correcta, relanzar con:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions
```

## Calibracion precisa multi-monitor (recomendado)

Para que funcione mejor sin importar donde este puesta la camara, corre una calibracion
guiada. El sistema mueve el cursor por puntos de cada monitor: miras el cursor y presionas
`Espacio` para guardar muestra.
Ahora la guia principal de calibracion es el **dot flotante de gaze** (no mueve tu mouse real).

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration
```

Controles en calibracion:

- `Espacio` o `s`: capturar muestra en el punto actual
- `n`: pasar al siguiente punto
- `c`: limpiar muestras
- `Enter`: entrenar y guardar perfil
- `q` o `Esc`: salir sin guardar
- `,` o `k`: entrar/salir de calibracion en caliente
- `p`: reiniciar calibracion desde cero (misma sesion)
- `.`: alternar acciones reales (modo seguro/ejecucion) en caliente

Despues, el perfil se carga automaticamente por `layout_hash` del escritorio.
Durante calibracion, cada muestra usa promedio de varios frames para reducir ruido.
Por defecto, al presionar `Enter` se guarda y pasa a **validacion post-calibracion** antes
de dejar ejecutar acciones reales.
El modelo de calibracion ahora usa regresion polinomica de 2do grado + regularizacion ridge
y edge weighting (mas peso a bordes/esquinas), para acercarse mas al comportamiento de
implementaciones de referencia en la comunidad.
Al guardar, se puede fusionar con calibraciones anteriores del mismo layout (activo por defecto).
El sistema compara modelo "actual" vs "fusionado" y guarda automaticamente el que tenga menor RMS.
Los logs ruidosos de MediaPipe/TFLite (clearcut/inference_feedback) se filtran por defecto.
Si queres verlos para debug, usar `--verbose-runtime-logs`.

Si queres recalibrar acumulando historial:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration --merge-calibration-history
```

Si la calibracion se arruino, borrar historial del layout actual y recalibrar limpio:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration --reset-calibration-history --no-merge-calibration-history
```
Si la calibracion guardada tiene error muy alto, el runtime la desactiva automaticamente para evitar inestabilidad.

## Validacion post-calibracion

Despues de guardar, el dot flotante muestra puntos de validacion. Mira el dot y presiona
`Espacio` o `s` para medir cada punto.

El sistema calcula:

- RMS global
- p95 global
- acierto de monitor
- RMS/p95/acierto por monitor

Si el monitor es correcto pero el punto queda corrido dentro de la pantalla, el runtime aplica
por defecto una segunda etapa `fine_screen_warp`: una correccion geometrica determinista en
coordenadas de pantalla entrenada con los puntos de validacion. Esta correccion se guarda en el
perfil y se puede desactivar con `--no-fine-screen-warp`.

Si pasa el gate, entra a control. Si falla, vuelve automaticamente a calibracion con solo los
puntos malos para repetirlos; no hace falta rehacer todo. Para evitar loops infinitos, por
defecto solo reintenta una ronda y luego queda en control SAFE con acciones bloqueadas. Se puede
ajustar con `--validation-max-retries N`.

Gate por defecto:

- RMS <= 220 px
- p95 <= 380 px
- acierto de monitor >= 95%

Acciones reales quedan bloqueadas si `--require-validation-for-actions` esta activo y la
calibracion no paso validacion. Para diagnostico se puede desactivar:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --no-require-validation-for-actions
```

Si queres guardar y entrar a control sin validacion post-calibracion:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration --no-validate-after-calibration
```

Si queres una validacion mas larga:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration --validation-points-per-monitor 9
```

## Gramática fija inicial

| Entrada | Accion |
|---|---|
| Mirar una ventana estable ~350 ms | Arma esa ventana como objetivo |
| Puño cerrado | Agarra la ventana mirada |
| Puño sostenido + mover mano | Mueve la ventana por el escritorio virtual, incluso entre monitores |
| Palma abierta durante drag | Suelta la ventana |
| Palma abierta + stroke arriba/abajo | Scroll en la ventana mirada; el retorno de la mano se ignora para evitar scroll inverso accidental |
| Dos manos visibles + separar | Zoom in del contenido de la app (`Ctrl+wheel`) |
| Dos manos visibles + juntar | Zoom out del contenido de la app (`Ctrl+wheel`) |
| Point / apuntar + gesto de tocar | Click en el control interactivo mas cercano al punto de mirada dentro de la ventana armada |

Notas de control:

- El scroll usa modo `stroke/clutch`: iniciar con palma abierta, mover en la direccion deseada, volver la mano a una posicion comoda sin soltar; ese retorno no envia scroll inverso. Para cambiar de direccion, soltar palma y empezar un nuevo stroke.
- Drag solo mueve mientras el gesto estable siga siendo `fist`; si el detector parpadea a `unknown`, la ventana queda tomada pero no salta.
- Dos manos no mueve ni redimensiona ventanas: solo hace zoom del contenido.
- El puño es la unica forma de mover ventanas. Antes de mover una ventana maximizada, el runtime la restaura y usa `SetWindowPos` para evitar arrastre fisico del mouse.
- El movimiento con puño tiene snap determinista por monitor: borde izquierdo=dock mitad izquierda, borde derecho=dock mitad derecha, borde superior=maximiza dentro del monitor.
- `Point` no clickea solo por apuntar: primero arma el punto y el click ocurre cuando el indice/mano hace un "air tap" hacia abajo o hacia la camara. Usa snap determinista por UIA cerca del punto de mirada y limitado a la ventana armada; si no encuentra control, hace fallback al punto de mirada.
- El overlay muestra `raw->stable` para cada mano. Ejemplo: `h0:left:point->none0.90!edge` significa que MediaPipe/geometria vio `point`, pero la mano fue bloqueada por estar en borde.
- Las manos pasan por quality gate antes de accionar: confianza, margen de borde, salto brusco, tamaño de palma y oclusion entre manos.

## Seguridad

- Las acciones reales estan detras de `--execute-actions`.
- La ventana del propio overlay se ignora como objetivo.
- Si no hay mano visible, el estado vuelve a `IDLE`.
- Las acciones destructivas como cerrar/borrar no estan habilitadas en esta fase.
- El LLM no entra en el loop.

## Ajustes utiles

Mas seguimiento de ojo, si la camara/luz lo soportan sin bajar FPS:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --face-every-n 2
```

Mas influencia del ojo dentro de la region de cabeza:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --gaze-gain-x 0.85 --gaze-gain-y 0.55
```

Menos temblor del ojo:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --gaze-deadzone 0.045
```

Volver a solo cabeza, para comparar:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --no-iris-refine
```

Desactivar auto-centrado (solo para diagnostico/comparar):

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --no-auto-center
```

Hacer auto-centrado mas rapido cuando cambias de postura:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --auto-center-alpha 0.06
```

Ajustar sensibilidad del click con `point`:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --point-tap-threshold-norm 0.10 --point-tap-release-norm 0.045
```

Ocultar cursor de mirada o mini-mapa (si queres overlay mas limpio):

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --no-gaze-pointer --no-desktop-map
```

Hotkeys globales (q/Esc fuera de foco) vienen apagadas por defecto. Si las queres:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --global-hotkeys
```

Si queres comparar sin modelo calibrado:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --no-use-calibration
```

Cambiar el umbral maximo permitido de error (RMS en pixeles):

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --calibration-max-rms-px 300
```

Cambiar cuantos frames se promedian por muestra de calibracion:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration --calibration-avg-frames 12
```

Si queres salir al guardar en vez de continuar directo a control:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --run-calibration --no-control-after-calibration
```

Mostrar el punto de mirada tambien en todo el escritorio (cursor del sistema), no solo en overlay
(apagado por defecto):

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --show-system-gaze-pointer
```

Mostrar un punto flotante de gaze en escritorio (sin mover tu mouse real):

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --show-desktop-gaze-dot
```

Mas suavizado para reducir temblor lateral:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --gaze-smooth-alpha 0.12 --gaze-max-step-px 110
```

Mas sensible para mover ventanas:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --drag-gain-x-px 3200 --drag-gain-y-px 1800
```

Menos sensible para scroll:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --scroll-gain 2400
```

Scroll mas firme, con retornos de mano ignorados y pasos limitados:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --scroll-gain 3000 --scroll-rearm-threshold-norm 0.014 --scroll-max-wheel-delta 300
```

Ventanas mas suaves al arrastrar:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --drag-smoothing-alpha 0.35 --drag-max-step-px 140
```

Dos manos: zoom menos nervioso:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --two-hand-zoom-step-ratio 0.16 --two-hand-zoom-cooldown-s 0.30
```

Puño: ajustar margen de snap a bordes:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --window-snap-edge-px 96
```

Puño: desactivar snap de bordes:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --no-window-snap
```

Point: buscar controles en un radio mayor:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --point-snap-radius-px 260
```

Gestos mas rapidos, pero menos filtrados:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --gesture-enter-frames 1 --gesture-exit-frames 1
```

Gestos mas estrictos para evitar falsos positivos:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --gesture-enter-frames 3 --gesture-exit-frames 2 --gesture-min-confidence 0.62
```

Permitir manos mas cerca del borde de la camara:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions --hand-edge-margin 0.015
```

Mas estricto para seleccionar ventana mirada:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --target-stable-ms 600
```

## Gate sugerido antes de seguir

- Overlay identifica la ventana mirada correcta al menos 9/10 intentos.
- Puño mueve ventana sin soltar inesperadamente durante 2 minutos.
- Palma hace scroll en la ventana mirada sin activar drag.
- Puño mueve la ventana entre monitores y activa snap lateral/superior en bordes.
- Dos manos solo hace zoom del contenido, sin mover la ventana.
- Point clickea el control cercano correcto al menos 8/10 intentos.
- Cero acciones sobre una ventana no mirada.
