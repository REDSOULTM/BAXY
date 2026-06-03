# Perfeccionamiento del subsistema de cámara — reporte 2026-06-01

> Investigación + auditoría multi-agente (25 agentes, verificación adversarial de
> licencias) → plan de 16 mejoras priorizadas → aplicación de las de alto-impacto
> y bajo-riesgo verificables OFFLINE, con un gate medido por cada una.
> Separación honesta hechos / pendientes-de-medir-en-vivo (CLAUDE.md #3, #3.5).

## Veredicto de la auditoría

El subsistema `gemma4_agent/vision_input/` está **sano en lo medular**: cumple las
4 restricciones duras (100% determinista geometría+FSM sin LLM por frame; CPU /
0-VRAM; privado, no persiste video; **todas** las deps comercial-OK). El OneEuro
estaba bien implementado (verificado contra Casiez 2012). NO hay contaminación de
licencia. Lo que se arregló son bugs latentes, gates muertos y robustez.

## Aplicado y MEDIDO (hechos, con test que pinea el gate)

| # | Cambio | Archivo | Gate medido |
|---|---|---|---|
| P1 | Guard de cara subido `<264`→`<478` (cierra IndexError latente al leer landmark 362) | `pointer.py` | Cara parcial (300 pts) → `None` sin crash ✅ |
| P2 | Modelo de confianza de gaze **alcanzable** (antes: piso 0.47 binocular / 0.92 fijo monocular → `min_confidence` muerto). Ahora binocular-en-acuerdo > monocular; EAR invalida ojo cerrado | `gaze.py` | monocular < binocular y < 0.35 ✅; ojo cerrado → `None` ✅ |
| P3 | Guard de timestamp no-monótono en OneEuro (timestamp repetido/atrás colapsaba dt→explosión del cursor) | `pointer.py` | timestamps `[…,0.066,0.066,0.040]` no producen salto ✅ |
| P4 | Cámara: `CAP_PROP_BUFFERSIZE=1` (frame fresco) + reintento tolerante a glitch UVC (antes: 1 frame malo mataba el loop) | `camera.py` | retry mockeado recupera ✅; desconectada → error claro ✅ |
| P5 | Watcher de presencia: debounce tolerante a parpadeos (antes: 1 frame caído reiniciaba el reloj → evento podía no emitirse nunca) + validación de args + guard timestamp | `watchers.py` | tren ruidoso `1,1,0,1,1` SÍ emite `face_entered` ✅; debounce<0 → ValueError ✅ |
| P6 | Guard de degeneración en gestos: landmarks colapsados → `unknown 0.0` en vez de `fist 0.92` (no dispara grab/click por basura) | `gestures.py` | 21 puntos idénticos → `unknown` ✅ |
| P9 | **Reconocedor de gestos en 2D** (descarta el z ruidoso de MediaPipe, issue #742) + reglas pinch/point más precisas | `gestures.py` | **matriz de confusión sobre fixture real** (abajo) ✅ |
| P13 | Calibración: evaluación **held-out (LOO-CV)** honesta (el `rms_error_px` actual es residual de entrenamiento = sobre-optimista) + selección de ridge por CV | `calibration.py` | LOO ≥ residual de entrenamiento ✅ |
| P14 | Cumplimiento comercial: `THIRD_PARTY_LICENSES.md`, pin + **sha256** de los `.task` (trazabilidad de licencia), limpieza del `.tmp` | `landmarks.py` + doc | modelos Apache + hash pineado ✅ |

### Matriz de confusión del reconocedor (P9) — fixture comercial-OK

Fixture: subset balanceado (250/clase) de **kinivi `keypoint.csv` (Apache-2.0)**,
landmarks 21pt reales etiquetados. Atribución en
`tests/fixtures/hand_landmarks/NOTICE.md`. Receta reproducible:
`python -m gemma4_agent.tests.fixtures.hand_landmarks.build_fixture`.

| Gesto | Accuracy ANTES (3D) | Accuracy DESPUÉS (2D + reglas) |
|---|---|---|
| palm | 0.928 | **0.992** |
| fist | 0.920 | **0.952** |
| point | 0.960 | **0.960** |
| **fist→pinch (falsos clicks)** | **14** | **0** |

Gate `≥0.95` por clase: **cumplido**. La confusión más dañina (fist leído como
pinch = click falso) eliminada al exigir que un pinch real mantenga los otros
dedos extendidos (definición del doc §7). Además: invarianza a rotación
in-plane / traslación / escala pineada en test.

**Esto responde tu pregunta original** ("¿por qué muestras manuales y no un
dataset?"): el fixture comercial-OK reemplaza las 50×4 muestras manuales para el
gate de **gestos** y lo hace reproducible/regresable. Lo que el fixture NO puede
dar (FPS y jitter en TU hardware) sigue siendo la corrida en vivo.

### Tests
- Suite `vision_input`: **82 verde** (57 baseline + nuevos), 0 regresión.
- Nuevos: `test_vision_input_robustness.py` (16), `test_vision_input_gesture_fixture.py` (6), +3 en calibración.
- `compileall` limpio. Cambios 100% scoped a `vision_input/` + sus tests.

## PENDIENTE de prueba EN VIVO con cámara real (hipótesis, NO declarado listo)

Estas mejoras son de alto impacto pero **riesgo medio**: su gate exige medir con
la webcam real (CLAUDE.md #3.5 — no se delega, pero un agente de código sin
hardware no puede ejecutarlas). NO se aplicaron para no regresar a ciegas.

| # | Mejora | Por qué necesita cámara real |
|---|---|---|
| P8 | Usar la `transformation_matrix` 3D de MediaPipe para yaw/pitch (hoy se calcula pero se ignora; se usa una heurística 2D más débil) | El signo de yaw/pitch (convención OpenGL vs OpenCV, issue #1642) hay que fijarlo en vivo o el cursor va al revés; el gate es jitter/linealidad sobre la misma secuencia |
| P11 | Snap-click: InvokePattern UIA antes de PostMessage (apps modernas ignoran WM_LBUTTON), DPI-awareness Per-Monitor-V2 | Hay que ver que el click cae en el botón a 150% de escala |
| P12 | Drift-correction de calibración por anclas (vs el EMA ingenuo que persigue su propia corrección) | Medir slippage en sesión larga |
| P7 | Throttle de CPU para MediaPipe (afinidad+OMP) análogo a `_ort_throttle` | El gate es que NO degrade la latencia del turno de voz (Whisper) mientras corre la cámara |
| Sweep | β del OneEuro 0.025→0.05-0.1 para head; ridge 1e-2 | El sweep sintético sugiere mejora; falta sensación de snap/lag real |

## Datasets — auditoría de licencias (producto se vende)

- **USABLES**: kinivi `keypoint.csv` (Apache-2.0, fixture, ya integrado);
  Zenodo 16420298 point/no-point (CC-BY-4.0); MediaPipe rps_data_sample (Apache).
- **RECHAZADOS** (no usar — registrados en `THIRD_PARTY_LICENSES.md`): HaGRID/v2
  (ShareAlike copyleft — NO "non-commercial", eso era una versión vieja), Jester
  (NC-ND), FreiHAND (research-only), InterHand2.6M (NC), Ultralytics (NC-SA +
  AGPL), leapgestrecog (NC-SA), WebGazer.js (GPLv3 — usar técnicas, no código).

## Fuentes (verificadas esta sesión)
- MediaPipe Gesture Recognizer / Hand Landmarker / Face Landmarker docs (ai.google.dev) — gestos, handedness espejada, z relativa.
- google/mediapipe #742 (z sin escala coherente), #1642 (convención OpenGL de la matriz), one_euro_filter.cc (guard de timestamp).
- Casiez et al. 2012 (One-Euro). PMC10966887 (ridge ~1e-2 en gaze webcam).
- kinivi/hand-gesture-recognition-mediapipe LICENSE (Apache-2.0); HaGRID README + arXiv 2206.08219 (licencia ShareAlike).
- Project Gameface (Google, Apache-2.0) — head-ray para cursor.
