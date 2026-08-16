# Guía de orador - Defensa de Carter como producto final

Presentación principal: `Carter_defensa_tesis_producto_final_costos_api.pptx`

Premisa obligatoria:

> La comparación se hace contra Carter final razonable, no contra Carter como prototipo actual.

Usa el estado actual solo como evidencia de viabilidad técnica. No abras la defensa diciendo "Carter hoy falla en X". Abre diciendo que el producto final que se propone ocupa un eje distinto frente a la competencia.

## Tesis central

Carter final tiene sentido porque combina cuatro cosas que la competencia suele separar:

1. Asistente local y privado.
2. Windows-first para una PC real.
3. Acciones directas sobre sistema, apps, archivos, terminal, ventanas, clipboard, registry read-only y Steam.
4. Verificación post-acción para reducir fake-success.

Frase fuerte:

> Carter final no compite por ser el agente más amplio. Compite por ser el asistente más confiable para operar una PC Windows local con acciones verificables.

## Guion por slide

### 1. Carter como producto final

"Voy a defender a Carter como producto final razonable, no como el estado parcial de desarrollo. La pregunta es si esa visión final tiene sentido frente a competidores ya existentes."

### 2. La competencia ya existe

"El punto de partida es honesto: ya existen agentes fuertes. Pero cada uno está optimizado para un eje distinto: GUI visual, código, workflows, frameworks o asistentes generales."

### 3. Agent-S

"Agent-S es muy fuerte si el problema se define como computer-use visual. Carter final no necesita ganarle en OSWorld para tener sentido. Carter final combina GUI con herramientas del sistema verificables y privacidad local."

### 4. Agentes code-first

"OpenHands, Open Interpreter y OS-Copilot son fuertes en código, shell y entornos de desarrollo. Carter final no intenta ganar por ejecución arbitraria; intenta ganar por acciones curadas, sandbox, confirmaciones y verificación."

### 5. Frameworks y plataformas

"LangGraph, AutoGen y AutoGPT son poderosos como infraestructura. Carter final no es un framework ni una plataforma de workflows; es un producto aplicado para operar una PC Windows."

### 6. Asistentes personales cercanos

"goose, Mark-XXXIX y openclaw se acercan más al espacio de asistente personal. Carter final se diferencia si mantiene foco Windows-first, privacidad local y verificación post-acción."

### 7. El vacío competitivo

"Esta matriz es el argumento principal. Ningún competidor cubre con la misma intención el paquete completo: Windows-first, local/private core, tools OS verificables, baja latencia, usuario normal y anti fake-success."

Sobre la fila de VRAM:

"La VRAM no depende realmente del framework, sino del modelo local que se use. goose no recomienda oficialmente 8 GB de VRAM en los archivos revisados; goose soporta proveedores cloud y también Ollama. OpenClaw tampoco fija una VRAM única; soporta modelos/proveedores y puede usar referencias locales como Ollama o LM Studio. Mark-XXXIX, como está implementado, depende de Gemini/cloud. Si se usan ChatGPT, Claude o Gemini, la VRAM local requerida es cero, pero aparece dependencia cloud/API."

Valores defensibles para decir:

- Agent-S: para resultados comparables se recomienda cloud; si se intenta local completo con LLM + grounding/VLM, pensaría en 24-48 GB o más.
- Open Interpreter: puede usar cloud o local; con modelos 7B/14B cuantizados, 8-24 GB según calidad deseada.
- AutoGPT: normalmente se usa con cloud/API; local es posible según configuración, pero no es su eje central. Pensar en 16-24 GB si se quiere un modelo local decente.
- goose: no encontré recomendación oficial de VRAM. Puede usar Ollama, así que la VRAM depende del LLM local elegido: un 7B/8B Q4 puede entrar cerca de 8-10 GB, un 14B suele pedir más margen, y modelos grandes tipo coder pueden ir a 20 GB o más.
- openclaw: tampoco encontré recomendación oficial de VRAM. Puede manejar providers/modelos, incluyendo referencias locales tipo Ollama/LM Studio, así que aplica la misma regla: depende del modelo.
- Mark-XXXIX: como está planteado en el repo, usa Gemini API; para el modelo no requiere VRAM local, pero depende de cloud.
- Carter final: 8 GB como mínimo viable para un 4B cuantizado; 12-16 GB recomendado para margen, contexto y mejor calidad local.

Sobre la fila de costo cloud/API:

"Estos costos no son una suscripción fija del competidor. Son una estimación de gasto mensual si se usa normalmente con modelos cloud por API. El supuesto usado en la tabla es 10M tokens de entrada + 2M tokens de salida al mes. Eso es un uso moderado de agente; uso con screenshots, audio, web search, best-of-N o workflows continuos puede multiplicarlo."

Supuesto de cálculo:

- Uso moderado: 10M input tokens + 2M output tokens al mes.
- OpenAI GPT-5.4: $2.50/M input y $15/M output -> aprox. $55/mes.
- OpenAI GPT-5.5: $5/M input y $30/M output -> aprox. $110/mes.
- OpenAI GPT-5.4 mini: $0.75/M input y $4.50/M output -> aprox. $16.50/mes.
- Claude Sonnet 4.6: $3/M input y $15/M output -> aprox. $60/mes.
- Claude Haiku 4.5: $1/M input y $5/M output -> aprox. $20/mes.
- Gemini 2.5 Flash: $0.30/M input y $2.50/M output -> aprox. $8/mes.
- Gemini 2.5 Flash-Lite: $0.10/M input y $0.40/M output -> aprox. $1.80/mes.

Lectura por competidor:

- Agent-S: normalmente se defiende con modelos frontier cloud para alto rendimiento. Con GPT-5.4/GPT-5.5 el uso moderado queda aprox. $55-$110/mes, y puede subir si usa múltiples rollouts, reflexión o visión intensiva.
- Open Interpreter: puede ser $0 si se usa local, pero con cloud normal queda aprox. $17-$60/mes según modelo. Si usa modelos frontier o muchas ejecuciones largas, sube.
- AutoGPT: suele depender de APIs cloud para workflows; con uso moderado queda aprox. $20-$110/mes, pero workflows persistentes pueden gastar más.
- goose: no tiene costo fijo; puede usar cloud, suscripciones o Ollama. Con local es $0 API; con cloud depende del modelo.
- Mark-XXXIX: como está implementado usa Gemini. En texto puede ser barato con Gemini Flash/Flash-Lite, aprox. $2-$8/mes bajo el supuesto; voz/live o visión pueden subir.
- openclaw: no tiene costo fijo; puede usar proveedores cloud, suscripciones o modelos locales. Con local es $0 API; con cloud depende del modelo.
- Carter final: el core local tiene $0 de API mensual. El costo real es hardware/electricidad; cloud sería opcional.

Fuentes usadas para precios:

- OpenAI API pricing: `https://openai.com/api/pricing/`
- Anthropic Claude pricing: `https://platform.claude.com/docs/en/about-claude/pricing`
- Gemini Developer API pricing: `https://ai.google.dev/gemini-api/docs/pricing`

### 8. Qué es Carter final

"Carter final no es solo un chatbot. Es una capa local de control para Windows que usa tools del sistema y verifica lo que hace."

### 9. Tesis en una frase

"La tesis es que un agente local Windows-first puede ser útil como producto si reduce el éxito fingido mediante control real del sistema y verificación post-acción."

### 10. Por qué gana como producto

"Carter final gana cuando el usuario quiere operar su PC, no construir una plataforma de agentes. Privacidad, Windows real, acción directa, honestidad, latencia y tareas cotidianas son el núcleo."

### 11. Arquitectura defendible

"La arquitectura no termina en la respuesta del modelo. Termina en herramienta, safety, verificación y reporte honesto. Esa es la diferencia técnica."

### 12. Superficie de PC

"El producto final tiene sentido porque toca una superficie real: apps, archivos, terminal, GUI, clipboard, registry, ventanas, Steam y memoria. No está limitado al navegador."

### 13. Frente a competidores

"La lectura honesta es que Carter final no gana todos los ejes. Pero sí gana un eje que importa: asistente local Windows-first verificable."

### 14. Por qué es tesis y no solo integración

"La contribución no es 'hice un asistente'. La contribución es construir y evaluar una arquitectura que reduce fake-success en tareas reales de PC."

### 15. Evidencia de viabilidad

"Aquí recién uso el estado actual: no para decir que el producto está terminado, sino para demostrar que la visión no es humo. Ya hay tools, tests, verifiers, safety, sandbox y matrix de evaluación."

### 16. Qué debe demostrar Carter final

"La tesis se vuelve fuerte si se mide: benchmark común, fake-success, GUI razonable, safety, latencia y demos honestas."

### 17. Claims correctos

"El claim correcto es preciso: Carter final prioriza acciones verificables sobre promesas. El claim incorrecto sería decir que Carter es mejor que todos o que ya resolvió todo."

### 18. Veredicto

"Carter final merece existir porque resuelve una combinación que la competencia no cubre bien: operar una PC Windows privada con acciones reales, verificables y honestas."

## Respuestas para preguntas difíciles

### ¿Por qué Carter si existe Agent-S?

Porque Agent-S es fuerte en GUI visual y benchmarks. Carter final tiene otra tesis: usar GUI cuando sea necesario, pero preferir herramientas del sistema verificables, privacidad local y baja latencia para tareas cotidianas de Windows.

### ¿Por qué Carter si existe Open Interpreter?

Open Interpreter es excelente para ejecutar código. Carter final se orienta a usuario de PC: acciones curadas, safety, sandbox y verificación. No todo usuario quiere que un agente resuelva su PC escribiendo código arbitrario.

### ¿Por qué Carter si existen goose, Mark-XXXIX u openclaw?

Porque Carter final debe especializarse más: Windows-first, control directo del sistema y verificación post-acción. Si no defiende esa especialización, se vuelve otro asistente más.

### ¿Cuál es la contribución de tesis?

Diseñar y evaluar una arquitectura local para PC donde las acciones del agente no se aceptan solo porque el modelo las narra, sino porque el sistema las verifica o las reporta como no verificadas.

### ¿Qué evidencia actual puedo mencionar sin debilitar el argumento?

Menciona la evidencia como prueba de viabilidad:

- 55 tools registradas.
- 131 tests verdes.
- Tool registry con verifiers y destructive flags.
- Safety, sandbox, memoria local y verificación.
- Matrix de evaluación de 540 casos.

No lo presentes como "Carter ya está final". Preséntalo como "ya existe una base técnica que hace plausible el producto final".

### ¿Qué frase debo evitar?

Evita:

> Carter hoy ya le gana a todos.

Usa:

> Carter final tiene sentido porque gana un eje específico: operación local verificable de una PC Windows.

## Cierre recomendado

"Mi defensa no es que Carter sea el agente más general del mercado. Mi defensa es que Carter final ocupa un espacio que los competidores no cubren con la misma combinación: privacidad local, Windows-first, herramientas reales del sistema y verificación para no fingir éxito."
