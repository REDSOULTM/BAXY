# C03 — inicialización del remuestreador antes del lector JSONL

Fuente164: VoiceEngine y DSP147 conservados. main llama prepare_resampler antes
de _run_control_plane. El helper usa el remuestreador existente con 48 muestras
vacías a48kHz; no abre dispositivos, cambia DSP, umbrales ni plazos. Warmup de
LoopbackReference se conserva para clientes nativos sin el entrypoint JSONL.

161 agotaba voice.start60s en carga _fblas con el lock de voz retenido.
162 sólo preimporta scipy.signal antes de runpy: precarga2,000s,
voice.start4,438s, ready/listening/ttsReady/AEC true, cierre18,656s exit0 y stderr
vacío. Es diagnóstico sin volumen audible/UI y con wake no aprobado heredado.

163 reduce a subprocess con numpy y stdin abierto: isatty responde tanto con
os.read como ReadFile; import SciPy bloquea10s con ambos. Se rechaza que baste
cambiar el lector o que os.isatty por sí solo explique el bloqueo. No se afirma
stack C gfortran específico; sólo inicialización nativa y lectura concurrente.
La documentación OpenBLAS describe bloqueo gfortran/pipes en otro host Java:
https://github.com/OpenMathLib/OpenBLAS#considerations-for-using-the-library-from-java
Sirvió como hipótesis, no como evidencia exacta del mecanismo de BAXY.
Biblioteca consultada por índice/inventario: sin título específico SciPy/BLAS/stdin.

Regresión real en proceso frío: el main/lector originales reciben probe con stdin
abierto y ejecutan SciPy; sin164 falla tras10s (1failed11,03s), con164 responde.
Suites dueñas lifecycle/protocol + siete de voz:191pass,0skips,19,14s.
Se conserva main y la lectura originales en la prueba; sólo el dispatcher del
modelo se sustituye por la operación de DSP. No simula SciPy ni cierra stdin.
No es aprobación integrada. Siguiente165 mismo sidecar161 con fuente164 y sin
precarga experimental; después Fast y producto real si cumplen.

165 producto164 sin precarga diagnóstica: catálogo5,140s/status4,094s/speak0,110s/start4,281s; listening/AEC/ttsReady true. Exit0/cierre17,110s, stderr vacío; sin procesos propios pendientes. Wake no aprobado sigue fuera de aceptación.
