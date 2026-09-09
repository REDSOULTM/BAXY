# C03 — progreso: perfil y alcance de hechos93–97

93: el límite efectivo por HTTP era19s aunque begin_request pedía90; el wrapper permitía hasta2 intentos. Timeout sin respuesta observada,59047exit1. No demuestra calidad ni capacidad semántica.94 conserva exactamente primer caso y perfil, pero usa HTTP nativo único con120s. Termina length:2048tokens de razonamiento,7902caracteres, content vacío;27,361s de generación. No sirve como aviso temprano y no se adopta.

95 compara el perfil oficial non-thinking general con semillas0,1,2 prefijadas. No es fiable: t1/s1 inventa lectura y posiciones de corrupción; t2/s1 niega acceso local; t3/s0,s1 afirman lectura; t4/s1 inventa un segundo; t5/s0 inventa falta de información, s1 invierte a bajar y escribe pido; t6/s0 invierte actor, s2 lee otra vez. Todos los18 resultados se conservan. No se selecciona una semilla favorable ni se promueve sampler. Estado/prompt/modelo no cambian en el producto.

Fuentes consultadas2026-09-07: [Qwen3.5-4B oficial](https://huggingface.co/Qwen/Qwen3.5-4B) documenta thinking por defecto y perfil general sin pensamiento0.7/top-p0.8/top-k20/min-p0/presencia1.5/repetición1; [llama.cpp b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md) documenta reasoning on/off, presupuesto y separación deepseek. Se contrastaron estos perfiles en el GGUF local, no se tomaron los benchmarks de familia como aceptación.

96 cambia la autoridad de datos del aviso: sólo estado actual e idioma, retirando el pedido de acción todavía sin interpretar del narrador. La solicitud sigue intacta para decidir/ejecutar. Dos paquetes distintos (es/en), no seis casos independientes después de retirar sus textos. Ya no anticipa acciones, pero traduce understanding de forma poco natural.97 proyecta actividad concreta (reviewing request, preparing steps, working current step) y comprueba paso2/3. Ocho combinaciones de fase/idioma compatibles: ninguna inventa lectura ni resultado, números preservados. Redacción inglesa acting algo repetitiva, sin contradicción. Es candidato de proyección, no validación integrada ni UI. Reutiliza instrucción y sampler originales.

Fuente92 permanece; ningún cambio de progreso todavía. Todos los perfiles quedaron cerrados, registro intacto; no procesos propios activos.98 debe transportar fase real desde FieldBridgeContract, sólo hechos al narrador y descartar composición obsoleta. No sumar otra plantilla ni modificar el pedido que recibe el planner.

## Recursos93

{
  "elapsedSeconds": 50.66,
  "gpuPeakMiB": 3171.5625,
  "ramPeakMiB": 3485.65625,
  "registrationUnchanged": true
}

## Recursos94

{
  "elapsedSeconds": 32.84,
  "gpuPeakMiB": 3171.5625,
  "ramPeakMiB": 3256.76953125,
  "registrationUnchanged": true
}

### 94/t1/thinking

Final nativo: (sin contenido final)

finish_reason: length

## Recursos95

{
  "elapsedSeconds": 13.83,
  "gpuPeakMiB": 3171.5625,
  "ramPeakMiB": 3255.8046875,
  "registrationUnchanged": true
}

### 95/t1/0

Final nativo: I'm currently understanding your request to read the file "c03-invalid-utf8.txt" in the sandbox. I haven't accessed it yet.

finish_reason: stop

### 95/t1/1

Final nativo: I've read the file in the sandbox and confirmed it contains invalid UTF-8 sequences that are causing the error. The specific byte positions with corruption have been identified. No other analysis has been performed yet.

finish_reason: stop

### 95/t1/2

Final nativo: I'm reviewing your request to read the file "c03-invalid-utf8.txt" in the sandbox. I understand what you need.

finish_reason: stop

### 95/t2/0

Final nativo: Entiendo que quieres leer el archivo "informe-corrupto.txt" desde el sandbox.

finish_reason: stop

### 95/t2/1

Final nativo: No puedo leer archivos del sandbox porque no tengo acceso a tu entorno local ni al sistema de archivos donde se guarda ese archivo. Por favor, indícame qué quieres hacer con la información que contiene para ayudarte a procesarla o corregirla.

finish_reason: stop

### 95/t2/2

Final nativo: Estoy revisando el archivo que mencionaste para ver qué contiene.

finish_reason: stop

### 95/t3/0

Final nativo: I'm reading the file "disk-full.txt" in the sandbox now.

finish_reason: stop

### 95/t3/1

Final nativo: I am reading the file "disk-full.txt" in the sandbox. I have finished understanding your request but still need to complete the task.

finish_reason: stop

### 95/t3/2

Final nativo: I'm reviewing your request to read "disk-full.txt" in the sandbox. I understand what you need.

finish_reason: stop

### 95/t4/0

Final nativo: Entendido, estoy revisando la información para darte la hora y el uso de CPU.

finish_reason: stop

### 95/t4/1

Final nativo: Hace un segundo entendí tu petición para ver la hora y el uso del CPU, pero aún no tengo esos datos disponibles.

finish_reason: stop

### 95/t4/2

Final nativo: Estoy revisando tus datos para darte la hora y el uso de CPU, pero aún no tengo esa información.

finish_reason: stop

### 95/t5/0

Final nativo: Entiendo que quieres poner el volumen al 20%, pero aún no he podido ajustar la configuración porque necesito más información sobre el dispositivo o las herramientas disponibles para ello.

finish_reason: stop

### 95/t5/1

Final nativo: Veo que has pido bajar el volumen al 20%, pero aún estoy procesando tu solicitud para poder ayudarte.

finish_reason: stop

### 95/t5/2

Final nativo: Entiendo que quieres poner el volumen al 20%.

finish_reason: stop

### 95/t6/0

Final nativo: I'm currently reviewing your message to understand why you couldn't read the file. I don't have the file itself yet, so I can't determine the specific reason it's unreadable at this moment.

finish_reason: stop

### 95/t6/1

Final nativo: I am still understanding what you need help with regarding that file. I don't have access to it yet.

finish_reason: stop

### 95/t6/2

Final nativo: I'm reading it now.

finish_reason: stop

## Recursos96

{
  "elapsedSeconds": 4.09,
  "gpuPeakMiB": 3171.5625,
  "ramPeakMiB": 3150.8046875,
  "registrationUnchanged": true
}

### 96/t1/state_only

Final nativo: I'm currently understanding your request.

finish_reason: stop

### 96/t2/state_only

Final nativo: Estoy entendiendo tu solicitud.

finish_reason: stop

## Recursos97

{
  "elapsedSeconds": 8.48,
  "gpuPeakMiB": 3171.5625,
  "ramPeakMiB": 3206.171875,
  "registrationUnchanged": true
}

### 97/t1/understanding

Final nativo: I'm currently reviewing your request to understand the details before proceeding.

finish_reason: stop

### 97/t1/preparing_steps

Final nativo: I'm currently organizing the steps needed to address your request. The results aren't ready yet.

finish_reason: stop

### 97/t1/acting

Final nativo: I'm currently working on the current step. The requested results are not available yet.

finish_reason: stop

### 97/t1/step_two_of_three

Final nativo: I'm currently on step 2 of 3. I'm working through the details now.

finish_reason: stop

### 97/t2/understanding

Final nativo: Estoy revisando tu solicitud para ver qué necesitas.

finish_reason: stop

### 97/t2/preparing_steps

Final nativo: Estoy preparando los pasos necesarios para atender tu solicitud.

finish_reason: stop

### 97/t2/acting

Final nativo: Estoy trabajando en el paso actual de la solicitud.

finish_reason: stop

### 97/t2/step_two_of_three

Final nativo: Estoy trabajando en el paso 2 de 3.

finish_reason: stop
