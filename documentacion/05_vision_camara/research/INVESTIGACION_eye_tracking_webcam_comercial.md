# Investigacion - eye tracking por webcam comercial-safe

Fecha: 2026-06-01.

Objetivo: mejorar precision del control por mirada sin hardware dedicado y sin romper la restriccion
comercial del producto. Solo se consideran rutas compatibles con venta si la licencia es permisiva
o si el componente queda fuera del producto.

## Conclusiones

1. MediaPipe Iris no da el punto de mirada en pantalla. Da landmarks de iris/ojo y estimacion de
   distancia a camara; necesita una capa propia de calibracion/modelo para convertir eso a
   coordenadas del escritorio.
2. La ruta webcam mas fuerte no es "iris geometry only", sino appearance-based gaze: crop de cara
   u ojos -> red neuronal -> vector de mirada -> calibracion por pantalla.
3. Muchos repos buenos no sirven para vender tal cual por licencias GPL o non-commercial.
4. Las opciones permisivas mas interesantes para estudiar/integrar son:
   - L2CS-Net: MIT, gaze estimation appearance-based.
   - UniFace/MobileGaze: MIT para el componente gaze, pero hay que evitar submodelos GPL
     listados por el proyecto.
5. La mejora inmediata del stack original debe ser: backend gaze intercambiable + validacion
   numerica por monitor + calibracion robusta regional. No conviene seguir acumulando historial
   si no hay metrica por zona.

## Matriz

| Opcion | Calidad esperada | Licencia | Comercial | Decision |
|---|---:|---|---|---|
| MediaPipe Face/Iris + modelo propio | Media | Apache-2.0 | Si | Mantener como fallback/base |
| L2CS-Net | Media/Alta | MIT | Si | Mejor candidato OSS para prototipo |
| UniFace MobileGaze | Media/Alta | MIT para MobileGaze | Si, con cuidado | Revisar dependencias/modelos elegidos |
| WebGazer.js | Media | GPLv3 | No para producto cerrado | No integrar |
| GazeFollower | Media/Alta | CC BY-NC-SA | No | Descartado |
| RT-GENE | Alta historica | CC BY-NC-SA | No | Solo referencia tecnica |
| ETH-XGaze baseline/dataset code | Alta historica | CC BY-NC-SA | No directo | Solo benchmark/referencia |
| Tobii/Gazepoint hardware | Alta | comercial/proprietary | Depende licencia SDK | Opcion premium futura |

## Mejoras tecnicas a copiar al stack actual

### 1. Backend de gaze intercambiable

Crear interfaz:

```python
class GazeBackend:
    def detect(frame, face_landmarks) -> GazeFeatures:
        ...
```

Backends:

- `mediapipe_geometry`: actual, comercial-safe.
- `l2cs_onnx`: futuro, si se integra modelo MIT o entrenado propio.
- `manual_debug`: para reproducir calibracion y tests.

Esto permite probar modelos mejores sin tocar gestos, ventanas ni seguridad.

### 2. Calibracion por monitor, no solo global

El modelo global aprende todo el lienzo virtual, pero en tu setup hay monitores con posiciones
distintas y alturas distintas. Para mejorar precision:

- seleccionar monitor primero con yaw/head pose,
- entrenar un modelo local por monitor,
- si la confianza de monitor es baja, usar el modelo global como fallback.

Metrica requerida:

- RMS global,
- RMS por monitor,
- peor punto por monitor,
- tasa de acierto de monitor.

### 3. Validacion obligatoria post-calibracion

Despues de guardar calibracion, mostrar 5 puntos aleatorios por monitor y medir:

- distancia entre target y gaze predicho,
- error promedio,
- error p95,
- si falla, no activar acciones reales.

Esto evita "calibro, guardo basura y luego controla mal".

### 4. Repeticion de puntos malos

En vez de repetir todo:

- detectar los puntos con error mas alto,
- pedir repetir solo esos puntos,
- reentrenar,
- aceptar solo si baja RMS/p95.

### 5. Filtro temporal mejor que solo one-euro

Mantener one-euro, pero agregar:

- limite de velocidad en px/s,
- hold si hay blink/confianza baja,
- mediana corta de 3-5 frames antes del filtro,
- no actualizar modelo durante movimientos bruscos de cabeza.

## Plan recomendado

### Fase A - Precision del stack actual

1. Agregar reporte de precision por monitor. **Aplicado:** los reportes de
   `window_control` ahora incluyen `calibration.diagnostics` con RMS/p95/max global y por
   monitor.
2. Agregar validacion post-calibracion. **Aplicado:** despues de guardar calibracion, el
   runner entra a una fase de validacion guiada por dot y calcula RMS/p95/acierto de monitor.
3. Agregar repetir puntos malos. **Aplicado:** si la validacion falla, el runner vuelve a
   calibracion solo con los targets de mayor error o monitor equivocado.
4. Separar modelo global vs modelo por monitor.

Gate:

- acierto de monitor >= 95%,
- RMS por monitor <= 220 px,
- p95 por monitor <= 380 px,
- sin acciones reales si no pasa.

### Fase B - Backend L2CS/UniFace experimental

1. No instalar en runtime principal hasta confirmar licencia de pesos/modelos.
2. Probar en runner aislado.
3. Exportar ONNX si aplica.
4. Comparar contra `mediapipe_geometry` en el mismo protocolo de validacion.

Gate:

- mejora >= 20% en RMS/p95 frente al stack actual,
- FPS >= 20 CPU o degradacion aceptable,
- licencia de codigo y pesos confirmada MIT/Apache/BSD/CC0.

### Fase C - Modelo propio comercial-safe

Si L2CS/UniFace mejora pero los pesos/datasets no son limpios para venta:

1. usar arquitectura permisiva como referencia,
2. entrenar/fine-tunear con datos propios consentidos,
3. publicar licencia interna clara del modelo resultante.

## Fuentes

- MediaPipe Iris docs: https://github.com/google/mediapipe/blob/master/docs/solutions/iris.md
- L2CS-Net repo/licencia MIT: https://github.com/Ahmednull/L2CS-Net
- L2CS-Net paper: https://arxiv.org/abs/2203.03339
- UniFace licencias y creditos: https://yakhyo.github.io/uniface/license-attribution/
- UniFace PyPI: https://pypi.org/project/uniface/1.5.0/
- WebGazer licencia GPLv3: https://github.com/brownhci/WebGazer
- RT-GENE licencia non-commercial: https://open.qcr.ai/code/rt_gene_code/
- ETH-XGaze repo/licencia non-commercial: https://github.com/xucong-zhang/ETH-XGaze
