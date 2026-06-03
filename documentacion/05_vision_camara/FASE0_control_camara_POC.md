# Fase 0 - POC de control manos-libres por camara

Estado: implementado como subsistema aislado en `gemma4_agent/vision_input/`.

## Alcance

- Captura webcam con OpenCV.
- MediaPipe Tasks en CPU para mano y cara.
- Gestos deterministicos por geometria: `fist`, `pinch`, `palm`, `point`, `two_fingers`.
- Region de cabeza en lienzo virtual multi-monitor con one-euro filter.
- Overlay visible con indicador `CAMERA ACTIVE`.
- Reporte JSON/Markdown con FPS, matriz de confusion y jitter.

No ejecuta clicks, no mueve cursor, no llama al LLM y no persiste video ni frames.

## Dependencias

Instaladas/probadas en Python 3.10.11:

```powershell
python -m pip install -r requirements-camera.txt
```

La combinacion queda pinneada para no subir `numpy` a 2.x:

- `mediapipe==0.10.35`
- `opencv-python==4.11.0.86`
- `opencv-contrib-python==4.11.0.86`
- `flatbuffers==25.12.19`

Los modelos `.task` oficiales se descargan bajo `~/.gemma4/camera/models` al correr con
`--download-models`.

## Ejecucion

Overlay interactivo:

```powershell
python -m gemma4_agent.vision_input.poc --download-models
```

Por defecto usa `camera-index 0` con backend `msmf`, captura `640x480` y corre cara cada
4 frames (`--face-every-n 4`). La mano sigue en cada frame; la cara a ~7.5fps alcanza para
region/jitter del POC y este backend fue el que paso FPS en esta camara.
La ventana y el overlay muestran la camara activa como `cam <indice> | <backend> |
<resolucion>@<fps>`. Esa es la imagen que se esta midiendo.
Tambien muestra progreso por gesto como porcentaje y `muestras/objetivo`, por ejemplo
`fist: 40% (4/10)`.

Medicion headless de 20 segundos:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --no-window --duration 20
```

Listar indices de camaras disponibles:

```powershell
python -m gemma4_agent.vision_input.poc --list-cameras --camera-backend msmf
```

Relanzar usando otra camara:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --camera-index 1 --camera-backend msmf --stop-when-samples-complete
```

La camara del setup actual es el indice `0`, asi que el comando normal no necesita flags
extra:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --stop-when-samples-complete
```

Matriz de confusion rapida:

1. Ejecutar el overlay.
2. Mantener cada gesto frente a la camara.
3. Presionar `1` para `fist`, `2` para `pinch`, `3` para `palm`, `4` para `point`.
4. El runner toma 10 muestras por gesto por defecto.
5. En modo ventana, al completar `fist`, `pinch`, `palm` y `point`, el overlay muestra
   `GESTOS OK`. Manten la cabeza quieta: espera 1 segundo y mide jitter durante
   3 segundos por defecto.
6. Cuando el overlay muestre `JITTER OK`, presionar `q`/`Esc` guarda el reporte y cierra.
   El gate de precision sigue evaluando `fist`, `pinch` y `palm`, pero la recoleccion espera
   los cuatro gestos para no cortar la matriz antes de tiempo.
7. En modo `--no-window`, `--stop-when-samples-complete` cierra automaticamente despues de
   completar gestos y la ventana de jitter.

Para una corrida mas estadistica se puede subir manualmente:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --samples-per-gesture 50 --stop-when-samples-complete
```

Si queres probar la resolucion anterior:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --width 1280 --height 720 --stop-when-samples-complete
```

Los reportes quedan en `~/.gemma4/camera/reports/phase0_camera_*.json` y `.md`, salvo que se
use `--report-path`.

## Gate

El runner evalua:

- FPS sostenido >= 20.
- `fist`, `pinch`, `palm` >= 95% cuando sus filas tienen 10 muestras por defecto.
- Jitter RMS filtrado <= 80 px por defecto (`--jitter-gate-px`), medido en la ventana
  separada de cabeza quieta posterior a los gestos.

Si no hay muestras manuales suficientes para `fist`, `pinch` y `palm`, el gate de gestos
queda incompleto y la Fase 0 no pasa.
