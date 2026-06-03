# Reporte Fase 0 - Control por camara

Fecha de corrida local: 2026-05-31 (`America/Santiago`).

## Entorno

- Python: 3.10.11
- Monitores detectados: 3
- Layout hash: `5969e33aa3239a3c`
- Lienzo virtual: `(-1920, 0) -> (1920, 1944)`
- MediaPipe: 0.10.35
- OpenCV: 4.11.0.86
- NumPy: 1.26.4
- Backend: MediaPipe Tasks, CPU/XNNPACK

## Medicion headless automatica

Comando:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --no-window --duration 6 --warmup-seconds 1 --report-path .gemma4_phase0_probe.json
```

Resultados:

- FPS sostenido: **27.80**
- Frames medidos: **150**
- Pipeline promedio: **17.93 ms**
- Pipeline p95: **24.10 ms**
- Jitter de cabeza filtrado: **n/a** (`head_samples=0`)
- Matriz de gestos: **sin muestras manuales**

## Gate

- FPS >=20: **pasa**
- Gestos `fist`/`pinch`/`palm` >=95%: **incompleto** en la medicion headless
  (requiere muestras manuales por gesto)
- Jitter cabeza acotado: **incompleto** (no hubo cara detectada en la corrida headless)
- Gate global Fase 0: **NO PASA TODAVIA**

## Medicion interactiva inicial

Comando:

```powershell
python -m gemma4_agent.vision_input.poc --download-models --stop-when-samples-complete
```

Resultado observado con camara `0`, backend `msmf`, `640x480`, `face_every_n=4`:

- FPS sostenido: **29.73** (**pasa**)
- Pipeline promedio: **12.34 ms**
- Pipeline p95: **19.87 ms**
- Gestos `fist`/`pinch`/`palm`/`point`: **10/10 correctos** en las filas medidas
- Jitter viejo de sesion completa: **716 px** (**no valido para gate**)

El jitter se estaba midiendo durante toda la sesion, incluyendo el movimiento natural al hacer
gestos. Se ajusto el runner para separar la prueba: primero completa los gestos y despues mide
3 segundos con la cabeza quieta. Ese nuevo reporte es el que debe decidir si Fase 0 pasa.

## Medicion interactiva final

Reporte:

```text
C:\Users\usuario\.gemma4\camera\reports\phase0_camera_20260531_224914.json
```

Resultado con camara `0`, backend `msmf`, `640x480`, `face_every_n=4`:

- FPS sostenido: **29.61** (**pasa**)
- Pipeline promedio: **12.64 ms**
- Pipeline p95: **20.08 ms**
- Gestos:
  - `fist`: **100%**
  - `pinch`: **100%**
  - `palm`: **100%**
  - `point`: **100%**
- Muestras restantes: **0** en los cuatro gestos
- Jitter de cabeza quieta: **8.58 px RMS** con `head_jitter_source=steady_head` (**pasa**)
- Muestras de jitter quieto: **90**

Gate final:

- FPS >=20: **pasa**
- Gestos `fist`/`pinch`/`palm` >=95%: **pasa**
- Jitter <=80 px RMS: **pasa**
- Gate global Fase 0: **PASA**

Conclusion: Fase 0 queda validada en este hardware. Se puede avanzar a Fase 1: gestos hacia
acciones deterministicas, sin LLM en el loop de control.

## Fase 1 aplicada

Se agrego `gemma4_agent.vision_input.window_control` como POC de control fijo de ventanas:

- mirada/cabeza estable -> ventana objetivo via Win32
- puño -> agarrar/mover ventana
- palma abierta -> scroll o soltar drag
- dos manos -> resize/maximize/restore por distancia entre manos
- modo seguro por defecto, acciones reales solo con `--execute-actions`

Prueba segura:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models
```

Prueba con acciones reales:

```powershell
python -m gemma4_agent.vision_input.window_control --download-models --execute-actions
```
