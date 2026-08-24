# Optimización de recursos de BAXY — handoff vivo

## Alcance

Goal independiente solicitado el 2026-08-24: impedir que BAXY vuelva a dejar
Windows inutilizable por CPU, GPU o RAM. Goal 10 queda expresamente fuera de
esta sesión.

## Hechos medidos

- Hardware: Intel Core i9-12900HX, 16 cores/24 hilos; 31,8 GiB RAM; NVIDIA RTX
  4060 Ti con 16.380 MiB VRAM.
- Tras el bloqueo visible de Windows, el proceso dominante fue
  `python.exe -X utf8 -m baxy_mind`, PID 6492. La muestra corta lo midió en
  166,2 % de un core; el Administrador de tareas mostró 97–99 % total. Se mató
  el árbol BAXY exacto y se verificó que no quedó ningún proceso BAXY,
  `baxy_mind`, `llama-server` ni router.
- El bloqueo apareció inmediatamente después de que BAXY compusiera y hablara
  una respuesta real. `voice_output._PiperOnnxEngine` creaba
  `onnxruntime.InferenceSession` sin `SessionOptions`: ORT podía crear un hilo
  por core físico y mantenerlos en spin después de la primera síntesis.
- La evidencia heredada ya documentaba el mismo mecanismo: tres ONNX sin
  `SessionOptions` usaron los 24 cores + spinning e inutilizaron Windows. Véase
  `tests/data/historical_messages.jsonl:11177` y
  `biblioteca/gemma4-agent/documentacion/03_voz_stt/research/plan_sherpa_parakeet_cpu_optimizacion.md:59-80,137-138`.
- Segunda fuga independiente: `PendingModelMessageQueue` reintentaba una
  composición fallida para siempre. La traza exacta contiene 542
  `compose.start`, 542 `compose.end` y 1.320 indicaciones visibles durante un
  único turno pendiente, con nuevas inferencias aproximadamente cada 8–10 s.
- Línea base sin BAXY: 18,7 GiB RAM libres; GPU 0 %, 1.102 MiB usados. El
  self-test de dos muestras del guardián tuvo picos de CPU total 3,7 %, GPU 1 %,
  RAM del sistema 41,6 % y cero procesos BAXY.

## Correcciones vigentes en el árbol

- `src/baxy_mind/resource_policy.py`: política única para ONNX CPU, 2 hilos por
  defecto, techo duro 4, ejecución secuencial y spinning intra/inter desactivado.
- Piper TTS, wake cascade y wake verifier usan esa política. Parakeet queda
  acotado a 1 hilo por defecto: en este i9 el corpus heredado midió ~230 ms con
  un hilo, mientras sherpa mantiene su pool en spin cuando está ocioso. El
  proceso fija además `OMP_WAIT_POLICY=PASSIVE` y
  `KMP_BLOCKTIME=0`.
- `llama-server` recibe `--threads 4`, `--threads-batch 4`, `--threads-http 2`,
  prioridad de generación baja y batch normal. El binario instalado confirmó
  esas opciones mediante `--help`, sin cargar el modelo.
- `main.py` limita build y publish a dos nodos MSBuild (`-m:2`), para que una
  recompilación previa al arranque tampoco ocupe todos los cores.
- La cola de prosa hace como máximo 3 inferencias automáticas. Al agotarlas
  retira el pendiente, conserva el fallo observable y desbloquea la interfaz;
  ya no existe una inferencia periódica infinita.
- `scripts/baxy_resource_guard.py`: monitor externo de prioridad alta. Corta
  sólo la familia de procesos BAXY tras presión sostenida: CPU total 85 %, CPU
  BAXY normalizada 70 %, RAM sistema 90 %, RSS BAXY 6 GiB, GPU 90 % o VRAM 85 %.
  Conserva muestras JSONL y recibo JSON.

## Validación hasta ahora

- `py -3.12 -m pytest tests/test_resource_policy.py tests/test_baxy_resource_guard.py -q`:
  5 passed.
- Prueba focalizada de argumentos `llama-server` + las anteriores: 6 passed.
- `dotnet test tests/Baxy.Integration.Tests/Baxy.Integration.Tests.csproj -c Release --nologo -v:minimal --filter FullyQualifiedName~ResourceGovernanceTests -m:2`:
  1 passed, 0 skipped, 0 failed.
- Guardián sin BAXY, 2 muestras: exit 0, ninguna acción.
- Prueba focalizada del límite de compilación: 1 passed; Ruff: verde.
- Corrida física R1 se detuvo voluntariamente antes del turno al descubrir que
  la consulta síncrona a `nvidia-smi` dilataba el reloj de CPU a ~2,6 s. El
  arranque alcanzó CPU BAXY 2,88 %, GPU 39 %, VRAM 22,3 %, RSS 2,81 GiB; no
  hubo saturación. Evidencia parcial: `physical_run_r1.jsonl`.
- El muestreo GPU ahora vive en un hilo independiente y la enumeración evita
  leer la línea de comando de procesos no Python. Self-test R4: 6 muestras en
  3,02 s (intervalo efectivo 0,50 s), CPU pico 4,2 %, GPU 1 %, sin acción.
- Corrida física R2: el guardián cortó el árbol antes del turno tras tres
  muestras de CPU total a 100 %. RSS BAXY pico 5,23 GiB, VRAM 25,01 %, GPU
  95 %. La atribución por PID de esa corrida era inválida porque se recreaba
  el objeto `psutil.Process` en cada muestra (su primera lectura siempre es
  cero); el total y el corte sí fueron válidos. Evidencia:
  `physical_run_r2.json` y `.jsonl`.
- El guardián conserva ahora el objeto de cada PID entre muestras. Como
  frontera independiente de cualquier biblioteca nativa, `baxy_mind` arranca
  con prioridad `BELOW_NORMAL` y afinidad dura; los hijos la heredan. La prueba
  aislada inicial confirmó afinidad `[0,1,2,3]`, prioridad 16384.
- Corrida física R3 atribuyó por fin el consumo de la fase de carga: `python -m
  baxy_mind` (PID 23620) sostuvo 368–406 % de un core durante el minuto
  observado; GPU se estabilizó en 7–10 %, VRAM 25,28 %, RSS BAXY 5,64 GiB. La
  aplicación se detuvo antes de que esa fase terminara. La correspondencia con
  `num_threads=4` de Parakeet permitió acotar el arranque, pero R4 posterior
  demostró que no era consumo permanente de reposo. Evidencia:
  `physical_run_r3.jsonl`.
- Corrección posterior a R3: Parakeet usa un hilo por defecto y la frontera del
  proceso se redujo a 2 CPUs lógicas. El segundo CPU queda disponible para el
  LLM local, pero sherpa ya no puede quemar cuatro cores en reposo.
- Validación focal posterior: `tests/test_resource_policy.py`: 5 passed. Los
  tests de selección de streaming quedaron sin coincidencias en el filtro; la
  suite amplia mostró un fallo ambiental previo por `rapidfuzz` ausente en el
  Python global, independiente del cambio (73 tests restantes pasaron).
- Corrida física R4, con Parakeet a un hilo y afinidad de la mente a dos CPU:
  106 muestras durante 58 s. Durante carga el Python pesado alcanzó ~192 % de
  un core, contenido por la afinidad. Desde la muestra 80 quedó realmente
  ocioso: últimas 20 muestras CPU BAXY promedio 2,93 %, máximo 4,51 %; GPU
  máximo 6 %. RSS residente final 5.628,48 MiB. Desglose: llama-server 2.855
  MiB; los dos Python pesados 1.097 + 842 MiB; Baxy.exe 201 MiB; WebView2 ~555
  MiB; Core 38 MiB. Evidencia: `physical_run_r4.jsonl`.
- Requisito explícito del dueño: no cargar LLM/STT/router bajo demanda ni
  descargarlos por inactividad; el primer turno no debe pagar carga fría. La
  optimización mantiene los modelos residentes y elimina sólo trabajo o
  memoria que no contribuya a latencia.
- Corrida física R5 aisló dos consumos residentes adicionales. Primero, la UI
  repintaba a 60 FPS un borde cónico y forzaba un render React completo del
  grafo neuronal en cada frame, aun en idle. Tras limitar sólo los repintados
  (borde 10/s; grafo 4/s idle, 20–30/s activo), WebView pasó de promedio 60,8 %
  de un core en R4 a 18,2 % en R5 (medianas 60,1→17,1; reducción ~70 %), sin
  ocultar ni congelar el estado. `npm run lint` y `npm run build`: verdes.
- R5 también demostró que el Python principal sostenía ~200 % de un core con
  micrófono activo. Causa: `SileroVad` importaba todo PyTorch únicamente para
  marshalling y el `OnnxWrapper` de terceros fijaba 1+1 hilos pero dejaba el
  spinning de ORT habilitado. Se sustituyó la envoltura, no el modelo: mismo
  `silero_vad.onnx`, estado `(2,1,128)`, contexto de 64 muestras, NumPy directo,
  sesión ORT propia de un hilo y spinning intra/inter apagado. Comparación real
  contra la envoltura oficial: 100 frames, diferencia máxima y media exactamente
  0. Prueba focal: 6 passed. R5 se detuvo voluntariamente antes del turno para
  aplicar esta corrección; evidencia parcial: `physical_run_r5.jsonl`.
- Corrida física R6 final: guardián `action=completed`, 766 muestras en 420,28
  s, cero PIDs matados y ningún límite sostenido cruzado. Todos los modelos se
  mantuvieron residentes. Reposo estable previo al turno (50 muestras): CPU
  BAXY promedio 0,76 %, máximo 2,02 %; GPU máximo 2 %; RSS 4.801 MiB. Frente a
  R4, los Python pesados bajaron de 1.097+842 MiB a 843+390 MiB al retirar
  PyTorch de voz.
- Dos turnos cruzaron la UI. `¿Quién eres?` resolvió la ruta ligera con pico CPU
  BAXY 5,95 %, GPU 2 %, RSS 4.932 MiB. La pregunta conversacional fue aceptada
  pero no produjo respuesta por el bloqueo de decisor expresamente fuera de
  este goal; durante 40 s no hubo fuga (CPU pico 9,17 %, GPU 5 %, RSS 5.033
  MiB) y la cola quedó acotada. Para ejercer el modelo residente sin reabrir
  Goal 10, se invocó su endpoint loopback: 29 tokens en 429,3 ms, respuesta
  correcta; llama-server alcanzó 48,6 % de un core y CPU BAXY pico 2,62 %. El
  muestreo GPU de 0,5 s no capturó una inferencia tan corta.
- Ventana post-inferencia de 60 muestras: CPU BAXY promedio 0,73 %, máximo 2,03
  %, RSS promedio 5.052,1 MiB y máximo 5.052,68 MiB, GPU máximo 2 %. Pico global
  R6: CPU total 44,7 %, CPU BAXY 11,48 %, RAM del sistema 56,8 %, RSS 5.052,75
  MiB, GPU 92 % aislado durante carga, VRAM total 25,69 %. No hubo 99 % ni pico
  GPU sostenido. Evidencia: `physical_run_r6.json` y `.jsonl`.

## Siguiente paso obligatorio

No lanzar BAXY sin iniciar primero el guardián. Hacer una corrida acotada de
arranque → reposo → una respuesta hablada → 60 s post-turno, conservar el JSONL
y demostrar que no cruza los límites. Después medir qué parte del RSS/VRAM
pertenece a App, mente, encoder y LLM y reducir sólo lo que siga siendo excesivo
sin reabrir calidad a ciegas.

## Árbol sucio ajeno a este goal

Al comenzar ya estaban modificados `artifacts/goal10/HANDOFF.md`,
`src/Baxy.App/MainWindowViewModel.cs` y `src/Baxy.App/MindSidecarClient.cs` por
la sesión anterior. Este goal sólo añade en `MainWindowViewModel.cs` el callback
terminal de la cola; el resto de esos diffs no se debe mezclar en su commit.
