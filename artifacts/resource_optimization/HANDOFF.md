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
  acotado a 4 hilos. El proceso fija además `OMP_WAIT_POLICY=PASSIVE` y
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
