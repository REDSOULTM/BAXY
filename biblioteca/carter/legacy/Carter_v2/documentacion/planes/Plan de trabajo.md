# Plan de trabajo

## Objetivo de esta nueva etapa

Reiniciar el proyecto como **Carter_v2** con una arquitectura correcta para construir un Jarvis real en Windows, preservando solo lo valioso de **Carter_v1** y dejando el resto como legado consultable.

La meta no es “seguir parchando Carter”.
La meta es **dejar de depender de un LLM que improvisa cómo hacer todo** y pasar a un sistema donde:

- el LLM entiende intención, planifica y decide
- las acciones comunes son capacidades deterministas
- la verificación es barata, factual y orientada a evidencia
- la GUI usa `UIA-first`
- la visión solo entra cuando UIA no alcanza
- el sistema está listo para volverse asíncrono y event-driven

---

## Síntesis de las investigaciones

### Prioridad dada a Claude

Se toma como base principal la investigación de Claude en:

- [Claude-Building a real Jarvis the definitive desktop agent architecture guide.md](/c:/Users/usuario/Desktop/ETC/Programacion/Carter%20OS%20AI/Carter_v2/documentacion/investigaciones/comparadas/Claude-Building%20a%20real%20Jarvis%20the%20definitive%20desktop%20agent%20architecture%20guide.md)

Su conclusión principal es la correcta:

**Carter debe pasar a un pipeline Planner -> Capability Router -> Deterministic Executor -> Verifier.**

Y además:

- el LLM no debe escribir scripts como camino principal
- las tareas simples deben resolverse por capacidades deterministas
- la GUI debe ser `UIA-first`
- la visión debe ser fallback
- la arquitectura debe separarse por módulos

### Coincidencias fuertes entre Claude, GPT y Gemini

Las tres investigaciones convergen en estos puntos:

- el problema ya no es “mejorar el prompt”
- el cuello real es arquitectónico
- Carter falla porque el LLM sigue improvisando demasiado
- hace falta un núcleo de capacidades deterministas
- la ejecución debe separarse del razonamiento
- la verificación factual sigue siendo valiosa
- `UIA-first` es el camino correcto para Windows
- la visión debe usarse bajo demanda
- el sistema debe migrar a una arquitectura más asíncrona

### Diferencias importantes

Donde no hay consenso completo:

- backend/runtime definitivo
- modelo textual definitivo
- cuánto conviene comprometerse ya con `TabbyAPI/ExLlamaV2`, `llama.cpp server`, `Ollama` o futuros backends

Decisión de trabajo:

**Carter_v2 no se acoplará todavía a un runtime/modelo único.**

Primero se construye la arquitectura correcta.
La elección definitiva de backend/modelo se hará después sobre una base v2 ya limpia.

---

## Decisión estratégica

La decisión correcta para el proyecto es:

**No rehacer el repo entero desde cero total.**

Sí hacer esto:

- mover la base actual a `Carter_v1/`
- crear `Carter_v2/` con código mínimo y limpio
- preservar ideas, no arrastrar deuda
- portar solo lo valioso cuando haga falta

La frase más cierta es:

**Carter necesita una arquitectura nueva por módulos, preservando solo ciertas piezas.**

---

## Qué preservar de Carter_v1

Estas piezas se consideran valiosas y se usarán como referencia o fuente de portado selectivo:

- sistema factual de `task_state`
- `verified_facts`
- `verification_targets`
- `completion_contract`
- bus/eventos `__CARTER_EVENT__`
- aprendizajes anti-loop y anti-repetición
- capa `UIA-first` ya iniciada
- adapters de backend como referencia conceptual
- benchmarks y harnesses como referencia de validación

Estas piezas **no** deben copiarse enteras a v2 en la fase inicial.
Deben reinterpretarse y portarse con intención.

---

## Qué NO portar de inicio a Carter_v2

No arrastrar desde v1 como default:

- `carter_core.py` tal como está
- el loop actual
- generación libre de PowerShell/Python como camino normal
- lógica reactiva acumulada
- repairs heredados
- prompts gigantes
- rutas que mezclan planning, ejecución, verificación y cierre en el mismo flujo
- visión como mecanismo frecuente

---

## Arquitectura objetivo de Carter_v2

### Núcleo

`Carter_v2` nacerá con estos módulos conceptuales:

1. `orchestrator`
   - recibe input del usuario
   - clasifica tipo de tarea
   - decide chat simple vs tarea ejecutable
   - pide plan corto al LLM cuando corresponda
   - despacha acciones al router

2. `planner`
   - convierte intención en pasos estructurados
   - no ejecuta nada
   - no escribe scripts como camino normal

3. `capability_router`
   - traduce pasos del planner a capacidades concretas
   - elige la capacidad correcta por dominio

4. `capability_core`
   - capacidades deterministas por dominio
   - inputs/output tipados
   - cada capability devuelve `result + evidence + errors + observations`

5. `verifier`
   - traduce evidencia a facts
   - decide si un contrato quedó satisfecho
   - puede cerrar sin LLM si la evidencia es suficiente

6. `memory`
   - working memory mínima
   - memoria factual
   - memoria procedimental futura
   - memoria semántica más adelante

7. `gui`
   - `UIA-first`
   - fallback visual explícito

8. `voice`
   - no entra en la fase 0
   - se diseña para fase posterior

---

## Principios obligatorios de Carter_v2

1. El LLM no genera código como mecanismo normal.

2. Las tareas simples deben resolverse con capacidades deterministas.

3. Toda salida del planner hacia ejecución debe ser estructurada.

4. La verificación debe ser lo más barata posible.

5. `UIA-first`, visión solo si falla UIA o no existe superficie accesible.

6. El backend LLM debe quedar desacoplado desde el inicio.

7. Se construye primero un sistema pequeño, verificable y extensible.

---

## Fases de trabajo de Carter_v2

### Fase 0: Renacimiento del repo

Objetivo:

- congelar v1 como legado
- crear v2 mínima
- limpiar superficie mental y técnica

Entregables:

- `Carter_v1/` con el proyecto actual
- `Carter_v2/` con esqueleto mínimo
- docs de transición

### Fase 1: Núcleo mínimo ejecutable

Objetivo:

- tener un orquestador mínimo
- capability registry
- contrato simple de acción y evidencia

Capacidades iniciales:

- `system.get_gpu_info`
- `system.get_audio_device`
- `process.start_app`
- `process.stop_app`
- `window.wait_for`
- `filesystem.create_folder`
- `filesystem.write_text`
- `filesystem.exists`
- `web.open_url`

Resultado esperado:

- consultas simples y acciones simples ya no dependen de scripts generados

### Fase de Estabilización (Abril 2026)

Objetivo:
- Consolidar la arquitectura modular tras el portado inicial.
- Eliminar mutaciones agresivas del SO.
- Centralizar configuración dispersa.
- Fortalecer el manejo de errores en memoria y herramientas.

Logros:
- Aislamiento total de estado global en tests (event bus y policy).
- Eliminación de `setx` y `taskkill /F /IM ollama.exe`.
- Configuración centralizada en `config.py` para variables de alto impacto (GGUF paths, speculative decoding, safety policies, workspace).
- Hardening de memoria: eliminación de fallos silenciosos mediante warnings con contexto.
- Hardening de ejecución: avisos de threads huérfanos en timeouts de herramientas.
- Alineación de documentación y `.env.example`.

### Fase 2: Planner estructurado + verificador factual

Objetivo:

- planner con salida JSON estructurada
- router a capabilities
- verificador factual reutilizando ideas de v1

Resultado esperado:

- Carter puede resolver tareas simples y medianas sin loops tontos

### Fase 3: GUI `UIA-first`

Objetivo:

- integrar inspección y acción UIA de verdad
- usar visión solo cuando UIA no alcance

Resultado esperado:

- navegación básica en apps Windows con mucha más robustez

### Fase 4: Tareas medianas reales

Objetivo:

- browser automation
- downloads
- documentos
- launchers básicos

Resultado esperado:

- Carter empieza a sentirse “operador”

### Fase 5: Async y background tasks

Objetivo:

- poder ejecutar tareas largas sin bloquear
- cancelación
- progreso
- base para experiencia Jarvis real

### Fase 6: Voz, memoria y robustez avanzada

Objetivo:

- STT/TTS
- interrupciones
- procedural memory
- visión más fina

---

## Qué se construye primero en Carter_v2

Lo primero no será voz, ni GUI profunda, ni benchmark grande.

Lo primero es:

1. tipos y contratos
2. capability base
3. registry
4. orchestrator mínimo
5. verificador factual mínimo
6. 8-10 capacidades deterministas esenciales

Eso ataca exactamente el dolor principal:

**dejar de fallar absurdamente en cosas simples.**

---

## Qué se pospone

Se pospone deliberadamente:

- visión pesada
- Office GUI profunda
- benchmarking masivo de modelos
- rutas multiagente complejas
- memoria vectorial avanzada
- voz en tiempo real

No porque no importen, sino porque hoy no son el cuello principal.

---

## Estructura inicial propuesta para Carter_v2

```text
Carter_v2/
  README.md
  pyproject.toml
  src/
    carter_v2/
      __init__.py
      main.py
      types.py
      event_bus.py
      orchestrator/
        __init__.py
        service.py
      planner/
        __init__.py
        schemas.py
      capabilities/
        __init__.py
        base.py
        registry.py
        system.py
        process.py
        filesystem.py
        web.py
      verification/
        __init__.py
        facts.py
        contracts.py
      adapters/
        __init__.py
        llm.py
        uia.py
  tests/
    test_orchestrator_smoke.py
    test_capability_registry.py
    test_system_capabilities.py
```

---

## Criterios de éxito de la primera etapa

Carter_v2 va bien si logra esto:

- `Dime qué GPU tengo` sin scripts generados
- `Dime qué dispositivo de audio está activo` sin scripts generados
- `Abre Steam` por capability determinista
- `Cierra Steam` por capability determinista
- `Crea un archivo hola.txt` por capability determinista
- `Abre la web de OpenAI` por capability determinista

Y todo eso con:

- cero parse errors
- cero JSON improvisado a mano
- cero Python/PowerShell generado como camino normal

---

## Decisión final de esta sesión

La sesión de hoy deja decidido esto:

- el proyecto activo pasa a ser `Carter_v2`
- el proyecto actual se congela como `Carter_v1`
- Carter_v2 empieza pequeño, limpio y modular
- se portará solo lo valioso, no la deuda
