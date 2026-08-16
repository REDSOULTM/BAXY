# Arquitectura y stack para convertir CARTER OS en un Jarvis real en Windows 11

## Resumen ejecutivo

La causa real de que **CARTER OS** todavía no se sienta como un Jarvis no es “el loop” ni “el prompt”. Es que el sistema sigue delegando en el LLM la **invención en tiempo real** de piezas que deberían existir como **capacidades deterministas**: cómo consultar estado del PC, cómo operar UI, cómo descargar, cómo cerrar, cómo verificar, y cómo evitar repetir. Ese patrón fuerza al modelo a improvisar protocolos, JSON, scripts y cierres formales incluso cuando el problema se resuelve con una llamada determinista. El resultado típico (que describes) es exactamente el que se espera: parse errors, JSON inválido, scripts rotos, auto-repairs, verificación cara y ciclos de 5–10 pasos para tareas triviales.

La tesis central de la solución es:

**Carter debe pasar de “LLM que inventa cómo hacer” a “sistema que ya sabe hacer, y el LLM solo decide qué hacer y con qué parámetros”.**  
En términos de arquitectura: un **Host/Orchestrator** (planner + dispatcher) sobre un **Capability Core** determinista, con **ejecución y verificación instrumentadas**, donde el LLM no escribe scripts salvo en un “sandbox” rarísimo y muy controlado.

Esto no es teoría: los sistemas de automatización de escritorio que empiezan a ser “prácticos” describen explícitamente que la robustez aparece cuando hay **integración profunda con el OS**, una capa **GUI–API** unificada, y un pipeline híbrido UIA+visión para control detection cuando UIA no alcanza. Un ejemplo concreto de investigación en Windows que formaliza esto (HostAgent + AppAgents, GUI–API action layer, y pipeline híbrido UIA+visión) es **UFO2**. citeturn5view0turn5view1

## Diagnóstico brutal del estado actual

Tu diagnóstico de fondo es correcto: hoy Carter está castigado por un “modo improvisor” del LLM. Y ese modo no se arregla con “más prompt” porque el LLM sigue siendo el lugar donde nacen demasiadas decisiones de bajo nivel.

Lo que **sí sirve** (y conviene preservar/reinterpretar) en tu base:

- La idea de **separar narrativa libre vs evidencia estructurada** y **cerrar por evidencia del mundo**, no por autoafirmación. Eso te mantiene honesto y es una ventaja real para un agente operador (no solo chatbot).
- `verified_facts`, `verification_targets` y `completion_contract` son (conceptualmente) lo correcto para evitar conclusiones falsas y para forzar “done means done”.
- Un canal/event stream como `__CARTER_EVENT__` es la semilla de trazabilidad y observabilidad: sin eso, nunca vas a poder depurar fallos GUI + latencia + acciones repetidas.

Lo que **sobra o está mal orientado** (no porque esté “mal escrito”, sino porque hace al sistema frágil):

- **El LLM como generador de herramientas/protocolos** (scripts PowerShell/Python, JSON “a mano”, mini-protocolos de verificación). Esto hace que tareas deterministas (GPU, procesos, archivos) dependan del talento del modelo y de su salida estructurada.
- **La verificación factual como costo fijo**. Si cada acción simple entra al “mismo rito” de verify/complete caro, el agente se vuelve lento y proclive a fallos por fatiga de tokens/formatos.
- **La UI como “screenshot-first”** (aunque ya intentaste moverte a UIA-first). La evidencia de la literatura reciente es consistente: percepción visual pura es ruidosa y costosa; incluso benchmarks GUI modernos muestran brechas grandes en “element grounding” y ejecución, lo que sugiere que conviene explotar al máximo señales estructuradas del OS/UI y usar visión como fallback. citeturn0search19turn0search31turn0search15

La implicación: tu hipótesis (“LLM planner + capacidades deterministas + UIA-first + visión bajo demanda + memoria útil + verificación fuerte + async/router”) es **mayormente correcta**, pero le falta una pieza clave: **una capa formal de acciones y evidencias** que haga que *cada capability* produzca pruebas verificables baratas y que el verificador no tenga que “reanalisar el mundo” con el LLM.

## Arquitectura recomendada

La arquitectura correcta para Carter (con tu base factual preservada) es un sistema de **planner + capability core + ejecución + verificación + cierre**, pero con una regla dura:

**El LLM no escribe código ni define protocolos; solo selecciona herramientas (capabilities) y llena parámetros bajo esquemas estrictos.**

Una forma concreta (y cercana a lo que funciona en sistemas tipo AgentOS) es:

### Orchestrator tipo HostAgent

Un proceso/daemon local (idealmente siempre activo) responsable de:

- Recepción multi-canal (texto/voz) y “control de sesión”.
- Clasificación de intención (rápida) y enrutamiento a “modo chat” o “modo tarea”.
- Planificación de alto nivel (cuando aplica) y conversión a un **plan ejecutable** (lista de acciones sobre capabilities).
- Coordinación multi-step, timeouts, cancelación, reintentos, y anti-loop.

Esta separación (HostAgent central + módulos especializados, con un plano de control que despacha subtareas) es exactamente el tipo de estructura que aparece cuando se intenta llevar CUAs (computer-using agents) a automatización Windows robusta. citeturn5view0turn5view1

### Capability Core determinista

Un registro de capacidades con:

- **Input schema** (JSON Schema) y validación previa a ejecución.
- **Ejecutor** determinista (Python + Win32/UIA/PowerShell/COM/Playwright/BITS).
- **Output** estandarizado: `result` + `evidence[]` + `observations[]` + `errors[]`.
- **Contrato de verificación** incorporado: cada capability declara cómo se verifica (rápido) y qué evidencias produce.

El punto es que `verified_facts` y `verification_targets` no desaparecen: se vuelven el **idioma nativo** de outputs de capabilities.

### Verificador y cerrador factual como servicios, no como rito

Tu “cierre factual” debe existir, pero con dos niveles:

- **Cierre determinista**: si la acción tiene prueba directa (archivo existe, proceso abierto, UIA event recibido, BITS job completado), se cierra sin LLM.
- **Cierre asistido por LLM**: solo cuando la evidencia es ambigua (p. ej., “¿ya quedó bonito el PowerPoint?”) o cuando la UI es visual/no estructurada.

Esto se alinea con la idea de que la automatización robusta reduce dependencia de “razonamiento sobre screenshots” cuando hay introspección del OS y eventos UIA disponibles. citeturn5view1turn4search10turn7search7

### Motor de ejecución event-driven y semi-asíncrono

Aquí tu intuición “Jarvis necesita async” es correcta por UX y por confiabilidad:

- UIA expone **eventos** (p. ej. focus changed, invoked, property changed). Si Carter aprende a esperar eventos y estados (en vez de “screenshot y adivina”), reduce loops y clicks redundantes. citeturn7search7turn7search27turn7search3
- Descargas/instalaciones pueden ir en background con BITS (o un manager propio), mientras el Orchestrator sigue conversando. BITS existe precisamente para transferencias en background con pausa/reanudación y baja interferencia. citeturn7search1turn7search0turn7search4

### Principio operativo

Un Jarvis usable en Windows se parece más a esto:

1) **Router** decide si es consulta simple, acción simple, o tarea compleja.  
2) Si es simple → **capability determinista** directa (0–1 llamadas LLM, idealmente 0).  
3) Si es compleja → planner LLM produce plan breve (acciones), pero cada paso es herramienta.  
4) Ejecutor corre acciones con verificación local; solo eleva a visión/LLM cuando falta señal.

Ese patrón reduce el “LLM overhead por step”, que en sistemas reales de escritorio se reconoce como un limitante y se ataca incluso con técnicas como planificación especulativa de múltiples acciones para reducir invocaciones. citeturn5view1

## Diseño del Capability Core determinista

La clave para no caer en “hardcodes por app” no es renunciar a dominios; es diseñar capacidades por **primitivas del entorno** (OS, procesos, ventanas, UIA, red, archivos) y usar UIA/visión solo como capa de interacción cuando no hay API.

### Capabilities mínimas “sí o sí” para un Jarvis real

Estas son las que más reducen tu dolor actual (porque reemplazan improvisación de scripts):

**Sistema y hardware**
- `system.get_hardware_summary()` (CPU/RAM/GPU/OS). Para GPU, Windows ya expone `Win32_VideoController` vía WMI/CIM; esto es determinista y verificable. citeturn3search18turn3search6
- `system.get_installed_apps()` (Registry/installer DB), `system.get_env_paths()`, `system.get_disks()`, etc.

**Procesos y ventanas**
- `proc.list()`, `proc.start(exe|appid|shortcut)`, `proc.kill(pid|name)`
- `win.list()`, `win.focus(window_id)`, `win.wait_for(title|process, timeout)`
- Estas capacidades alimentan verificación: “¿abrió Discord?” se verifica por proceso+ventana, no por narrativa.

**Archivos**
- `fs.create_folder()`, `fs.write_text()`, `fs.zip()`, `fs.open_path()`, `fs.exists()`, `fs.hash()`
- Todo esto es 100% determinista (Python stdlib + Windows Shell/Open).

**Red/descarga**
- `net.download(url, dest, mode=bits|http)`  
  Usar BITS como backend cuando importa robustez (pausar/reanudar, reboot-safe, bajo impacto). citeturn7search1turn7search0

**Navegador**
- `web.open(url)` (simple)
- `web.automate(task)` con backend Playwright para búsquedas, descargas, logins bajo control. Playwright provee APIs sync/async y manejo explícito de descargas vía eventos. citeturn3search13turn3search2

**Office/documentos**
- `office.pptx.create(deck_spec)` usando python-pptx para generar `.pptx` sin depender de PowerPoint instalado. citeturn4search0turn4search12
- `office.pptx.open(path)` para abrir el resultado (y opcionalmente, `office.powerpoint.com_*` si más adelante quieres automatización profunda vía el objeto Application del API de PowerPoint). citeturn4search1

**GUI (UIA-first)**
- `gui.find(selector)` (selector estructurado: control type, name, automation id, patterns)
- `gui.invoke(element)` / `gui.set_value(element, text)` / `gui.select(element, option)`  
  Este núcleo depende de UIA control types/patterns/properties, que Windows define precisamente para acceso programático a controles. citeturn0search24turn0search4turn0search8turn0search0

### Cómo evitar hardcodes por app sin volverte ciego

La salida práctica es introducir el concepto de **“UI Skills” aprendidos** (no hardcodeados), que se guardan como:

- Un **selector UIA** + fallback (texto/visión) + precondiciones (ventana activa, proceso).
- Evidencia típica de éxito (window title cambió, elemento desapareció, evento invoked, etc.). citeturn7search7turn7search27

Esto no es una lista de palabras clave; es un “procedural memory” verificable. Y se puede versionar y invalidar cuando falla (evitas intoxicación).

## GUI: UIA-first, visión bajo demanda y parsing estructurado

UIA-first es el camino correcto **en Windows** si tu objetivo es robustez y bajo costo de percepción. UI Automation es un framework de accesibilidad que da acceso programático a la mayoría de elementos UI y permite interacción sin depender de coordenadas. citeturn4search10turn0search24

El problema real es que UIA no cubre todo: apps con controles custom, juegos, canvas, overlays, algunos componentes Electron, etc. Ahí necesitas un sistema híbrido.

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["Accessibility Insights for Windows Inspect tool screenshot UI Automation tree","Microsoft UI Automation control patterns diagram","OmniParser GUI agent demo screenshot","UI-TARS GUI agent screenshot"],"num_per_query":1}

### Pipeline recomendado de control detection y acción

1) **UIA (primario)**  
   - Enumerar árbol, filtrar por control type, properties (Name, AutomationId, ClassName), y patterns (Invoke, Value, Selection…). citeturn0search12turn0search8turn0search4  
   - Suscribirse a eventos relevantes (focus changed, invoked, property changed) para sincronizar acciones y evitar loops. citeturn7search27turn7search7  
   - Herramientas de inspección como Accessibility Insights ayudan a entender qué expone UIA y depurar selectores. citeturn4search36turn4search3turn7search31  
   - Librerías Python disponibles: pywinauto (backend uia/win32) y wrappers UIAutomation dedicados. citeturn2search6turn2search4turn4search2

2) **Win32/input emulation (secundario, controlado)**  
   - Teclas, shortcuts y foco de ventana cuando UIA no expone bien un control.
   - Importante: esto debe estar “gobernado” por guardrails (no repetir, no spamear).

3) **Visión bajo demanda (terciario)**  
   - Para apps donde UIA no sirve (juegos, canvas, UIs no accesibles).  
   - Aquí tu hipótesis “visión solo fallback real” es clave para performance.

### Qué rol deben jugar MiniCPM-V, OmniParser, UI-TARS

- **MiniCPM-V** (y variantes) tiene como valor práctico que apunta a eficiencia (compresión del input visual a pocos tokens) para deployment, lo que lo vuelve razonable como “ojo bajo demanda” en GPU limitada. citeturn0search3turn0search11  
- **OmniParser** es especialmente relevante para tu problema: no intenta que el VLM “vea todo y decida todo”, sino que convierte screenshots en **elementos estructurados** (regiones interactuables + semántica) para facilitar grounding y reducir ambigüedad. En su planteamiento, mejora la capacidad de agentes basados en visión al entregar una representación más accionable. citeturn2search0turn2search10turn5view0  
- **UI-TARS** representa la apuesta “end-to-end screenshot→acciones” y se plantea como modelo GUI nativo. Es interesante como investigación, pero en un Jarvis práctico en Windows suele ser más seguro mantener UIA como primera opción y reservar modelos end-to-end para casos donde no hay estructura (por costo y por dificultad de verificación). citeturn0search35turn0search39

La síntesis, que coincide con arquitecturas AgentOS recientes: **fusión UIA + parsing visual** para cubrir interfaces diversas, no “screenshot-only”. citeturn5view1turn5view0

## Stack tecnológico recomendado

Voy a recomendar un stack pensando en: Windows 11, 16GB VRAM, latencia baja, salidas estructuradas confiables, y mínima fricción de despliegue.

### Backend/runtime (texto)

**Recomendación principal: TabbyAPI + ExLlamaV2 (EXL2) para el cerebro textual operativo.**

- ExLlamaV2 está orientado a inferencia local rápida en GPUs de consumidor, y TabbyAPI es el servidor oficial recomendado con API compatible tipo OpenAI. citeturn0search1turn1search7  
- TabbyAPI declara soporte de JSON schema/Regex/EBNF, speculative decoding con draft models y concurrencia con asyncio, que ataca directamente tus problemas de parseo/formatos y latencia por step. citeturn1search3turn1search3  

**Alternativa viable y simple: Ollama (si priorizas “funciona ya”).**

- Ollama corre nativo en Windows y expone API local; además ya soporta tool calling y structured outputs por JSON schema. Para tu caso, esto es crítico: si fuerzas al modelo a emitir bajo esquema, reduces JSON inválido y parse errors. citeturn6search3turn1search10turn1search2  

**Backends “Stack 3” (vLLM/SGLang): recomendables solo si aceptas WSL2/infra adicional.**

- vLLM tiene tool calling y structured outputs (JSON schema/grammar) muy potentes. citeturn0search6turn0search2turn0search22  
- Pero el soporte Windows históricamente ha sido más complejo (WSL2 y builds específicos), aunque existen esfuerzos para Windows. citeturn6search35turn6search7turn6search0  
- En el caso de SGLang/mini-SGLang, hay documentación que explícitamente indica limitación a Linux y recomienda WSL2/Docker por dependencias de kernels. citeturn6search12  

Para un “Jarvis producto” en Windows, mi lectura es: **TabbyAPI/ExLlamaV2 o Ollama** te dan el mejor balance entre rendimiento, confiabilidad estructural y operabilidad hoy.

### Cerebro textual

Tu hallazgo “Qwen3 14B fue el mejor cerebro operativo local probado” encaja con la orientación de Qwen3 hacia reasoning, instruction-following y capacidades agentic (según su documentación pública y model card). citeturn1search0turn1search16  

Dicho eso, para “Jarvis operador” hay dos perfiles útiles:

- **Generalista fuerte (ej. Qwen3 14B)** para planificación/razonamiento multilenguaje y decisiones de alto nivel. citeturn1search0turn1search16  
- **Coder/agentic-coder (ej. Qwen2.5-Coder 14B)** para cuando necesites generar o revisar “artefactos” (scripts, regex, transforms), pero **no** como mecanismo estándar para tareas simples. citeturn1search1turn1search5  

Mi recomendación concreta para Carter:

- Mantén un **solo cerebro principal** (Qwen3 14B o equivalente) para planificación y tool-calling.
- Añade un **cerebro auxiliar barato** (router/draft) solo si vas a explotar speculative decoding (TabbyAPI soporta draft models). citeturn1search3  

Lo importante no es “dos cerebros porque sí”, sino usar el cerebro principal **solo para lo que aporta**: decisiones y lenguaje; no scripts.

### Salidas estructuradas (anti-parse y anti-“JSON inválido”)

Este punto es no negociable: necesitas que el runtime soporte **constrained decoding** hacia JSON schema/grammar en serio (no “intenta escribir JSON”).

- Ollama: structured outputs por JSON schema. citeturn1search2turn1search14  
- TabbyAPI: JSON schema + regex + EBNF. citeturn1search3  
- vLLM y SGLang: structured outputs por JSON schema/regex/grammar, con guías específicas y backends de guided decoding. citeturn0search2turn0search22turn0search18  

Esto ataca directamente el síntoma “parse errors”, pero más importante: habilita que el LLM sea solamente **selector de herramientas**, no generador de mini-protocolos.

### Visión

- Mantén **UIA-first** y usa visión solo bajo demanda (tu Stack 2). Está alineado con la evidencia de que visual-only es ruidoso/caro y que sistemas robustos combinan UIA + visión. citeturn5view1turn0search15  
- Como “ojo”: MiniCPM-V puede ser razonable por su foco de eficiencia; OmniParser puede ser el “parser” que transforma screenshot→elementos para grounding. citeturn0search3turn2search0turn2search10

### Memoria

Para Jarvis, la memoria útil no es “más contexto”, sino **mejor separación de tipos**:

- **Memoria factual verificada** (tu `verified_facts`): TTL, timestamp, evidencia y fuente (WMI/UIA/fs/web).  
- **Memoria procedimental** (playbooks): secuencias de capabilities que funcionaron, con precondiciones y checks.  
- **Memoria semántica** (vectorial) solo cuando Carter deba trabajar con contenido (docs, notas, repos), no para decisiones operativas cortas.

La idea de integrar logs de ejecución y documentación como memoria recuperable aparece explícitamente en diseños AgentOS para Windows (integración continua de conocimiento y logs). citeturn5view1  

### Audio y experiencia Jarvis

Para voz natural + baja latencia local:

- STT: Whisper es un baseline robusto ampliamente usado; OpenAI describe su entrenamiento masivo y su uso multilenguaje. citeturn2search9turn2search12  
- Para hacerlo “Jarvis”, necesitas streaming/tiempo real: **faster-whisper** reimplementa Whisper con CTranslate2 y reporta mejoras de velocidad y memoria (incluye opciones de quantización). citeturn2search2  
- TTS local: Piper es un motor TTS local “rápido” orientado a correr offline. citeturn3search0turn3search7  

La arquitectura debe ser asíncrona para permitir: escuchar mientras ejecuta, barge-in (“para”), y cancelación de tareas; eso es condición UX de Jarvis, no un lujo.

### Observabilidad y benchmark

Tu `__CARTER_EVENT__` debería evolucionar a:

- **Trace por task** (span por action) con inputs/outputs/evidence.
- “Action ledger” para detectar repetición (mismo intento, mismo target, sin cambio de estado).
- Métricas: tasa de éxito, pasos hasta éxito, latencia por step, costo de visión (cuántas veces se activó), y ratio de “fallback”.

Esto no requiere una herramienta específica; requiere disciplina de instrumentación. Pero la motivación es clara: en automatización GUI, fallos típicos se agrupan (control detection, plan errors, etc.), y sin trazas no hay mejora sistemática. citeturn5view1turn0search19

## Roadmap realista de implementación

Voy a proponerte un camino por fases que maximiza “Jarvis usable” temprano y minimiza rework.

### Fase de estabilización

Objetivo: **matar parse errors y matar improvisación en tareas simples**.

- Migrar toda decisión LLM→acción a **tool calling con JSON schema** (Ollama/TabbyAPI/vLLM/SGLang lo soportan en distintos grados). citeturn1search2turn1search3turn0search22turn0search18  
- Congelar “LLM genera scripts” como estrategia default. Crear una sola capability `sandbox.run_code` para casos excepcionales, fuertemente restringida.
- Implementar 15–30 capabilities deterministas mínimas (system/proc/win/fs/net/web/office básico) y forzar que el LLM solo pueda operar sobre ellas.
- Redefinir tu “cierre factual” en dos niveles: cierre determinista (rápido) y cierre asistido (LLM) solo cuando no hay señal.

Resultado esperado: “Dime qué GPU tengo” deja de ser un caso donde el LLM inventa PowerShell; se vuelve una llamada determinista basada en Win32_VideoController, y es verificable. citeturn3search18

### Fase Jarvis MVP

Objetivo: **operador útil diario** para acciones simples y tareas medianas.

- UIA-first completo:
  - Selector UIA formal (tipo, nombre, automation id, patterns).
  - Métodos invoke/value/selection.
  - Event watchers para sincronización (focus changed, invoked, property changed). citeturn0search4turn7search7turn7search27
- Browser automation con Playwright para búsquedas y descargas cuando la web es parte del flujo. citeturn3search13turn3search2
- Descargas robustas con BITS como backend (cuando aplique). citeturn7search1turn7search0
- Office: generación de PPTX con python-pptx (sin depender de UI). citeturn4search0turn4search12
- Voz local: faster-whisper + Piper, con loop asíncrono y cancelación. citeturn2search2turn3search0

MVP “Jarvis usable” = Carter hace: abrir apps, navegar ventanas, mover archivos, descargar cosas, generar documentos simples, y contestar info del sistema, sin atascarse en loops ni romper JSON.

### Fase robustez avanzada

Objetivo: **GUI difícil + tareas largas sin intervención**.

- Integrar visión bajo demanda:
  - “Trigger conditions” claras: UIA no encuentra elemento, UIA tree vacío, superficie renderizada (DX/GL), canvas, etc.
  - Agregar OmniParser como etapa de parsing de pantalla para grounding. citeturn2search0turn2search10
- “UI Skills” aprendidos (procedural memory) con invalidación.
- Especulación/agrupación de acciones: reducir calls LLM por step (alineado con ideas tipo “speculative multi-action execution” en AgentOS). citeturn5view1
- (Opcional) ejecución aislada: virtual desktop o entorno separado para correr sin bloquear al usuario (esto existe como estrategia en AgentOS Windows para evitar interferencia en el escritorio principal). citeturn5view1

### Fase full Jarvis

Objetivo: híbrido local/remoto por clase de tarea (si lo aceptas), con policy explícita:

- Local por defecto para privacidad/latencia.
- Remoto solo cuando:
  - necesitas razonamiento pesado,
  - necesitas visión de alta calidad,
  - o el costo de fallar es alto y el usuario lo aprueba.

## Ejemplos concretos y veredicto final

### “Dime qué GPU tengo”

**Cómo debería resolverse internamente (sin improvisación):**

1) Router clasifica: *consulta simple de sistema*.  
2) Ejecuta `system.get_gpu_info()` → backend WMI/CIM `Win32_VideoController`. citeturn3search18turn3search6  
3) Evidence emitida:
   - `facts`: modelo GPU, driver version si quieres, VRAM si disponible.
   - `source`: `wmi/cim`.
4) Cierre determinista: respuesta textual + registrar en `verified_facts` con timestamp.

No hay JSON libre del LLM, no hay script generado, no hay verify caro.

### “Haz un PowerPoint de amor”

**Diseño recomendado (documento primero, UI después):**

1) Router: tarea de documento.  
2) Planner LLM produce un `deck_spec` *estructurado* (título, secciones, tono, número de slides, texto por slide, sugerencias de imágenes). Salida bajo JSON schema (Ollama/TabbyAPI). citeturn1search2turn1search3  
3) Capability determinista `office.pptx.create(deck_spec)` usando python-pptx: genera `.pptx` sin abrir PowerPoint. citeturn4search0turn4search12  
4) Verificación determinista:
   - archivo existe,
   - tamaño > umbral,
   - opcional: reabrir con python-pptx y chequear conteo de slides.
5) Capability `fs.open_path()` para abrirlo en el sistema.  
6) Cierre factual: `completion_contract` satisfecho por evidencia (archivo creado + abierto).

**Nota brutal:** hacer PPT “controlando PowerPoint por GUI” es innecesariamente frágil si tu objetivo es un `.pptx` final. El Jarvis real elige la vía determinista cuando existe.

### “Descarga X juego”

Aquí hay una tensión real con tu restricción “sin hacks por app”: instalar juegos casi siempre depende de launchers con flujos propios. La forma de mantenerlo generalista es:

1) Router: *download/install*.  
2) Planner define estrategia por capas:
   - Si hay URL directa y legal a instalador → `net.download()` (preferir BITS para robustez en background). citeturn7search1turn7search0  
   - Si es web-flow → `web.automate()` con Playwright, capturando eventos de descarga. citeturn3search2turn3search13  
   - Si requiere launcher → abrir launcher y navegar con UIA-first.
3) Verificación:
   - Descarga completada (BITS job completed / archivo hash / tamaño). citeturn7search0turn7search4  
   - Instalador ejecutado (exit code, proceso terminó, carpeta creada, app registrada).

Si el usuario pide “Steam” explícitamente, el sistema puede operar por UIA dentro del launcher sin hardcodear “Fall Guys”, pero el dominio “launcher-store” sigue siendo inherentemente UI-heavy.

### “Abre Discord y métete al canal X”

1) `proc.start("Discord")` + `win.wait_for(process="Discord")`.  
2) UIA-first:
   - encontrar “Quick switcher” o campo de búsqueda (si expuesto) y navegar.  
   - si UIA expone poco, fallback a atajos de teclado (estrategia genérica de input, no hardcode por canal).  
3) Verificación:
   - ventana activa con título/elemento que refleje canal (si UIA lo expone),
   - o evidencia visual bajo demanda (solo si UIA no da señal).

Para depurar selectores y eventos UIA en apps complejas, herramientas como Accessibility Insights son útiles (inspección + event monitoring). citeturn4search36turn7search31

### Veredicto final

La frase más cierta es:

**“Carter necesita una arquitectura nueva por módulos, preservando solo ciertas piezas”.**

Razón: tu base factual (task_state / verified_facts / verification_targets / completion_contract / evento) es valiosa y debe quedarse, pero el comportamiento Jarvis emerge cuando:

- las capacidades deterministas dejan de ser excepciones y pasan a ser el “camino feliz”,
- UIA y eventos se vuelven primera clase (no solo fallback),
- la visión se usa bajo demanda con parsing estructurado (no como retina siempre prendida),
- y el LLM queda encapsulado como planner/selector con salidas estructuradas (JSON schema/grammar) para eliminar el costo sistémico de parseo e improvisación. citeturn4search10turn7search7turn2search0turn1search3turn1search2