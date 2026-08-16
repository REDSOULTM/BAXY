# Carter v3 — Roadmap de Absorción de Competidores
**Fecha:** 2026-05-06  
**Basado en:** Auditoría técnica profunda de Open Interpreter, Agent-S, Windows-Use, PyWinAssistant, DirectShell, Mark XXXIX  
**Objetivo:** Absorber lo mejor de cada proyecto para que Carter sea el mejor asistente local Windows

---

## Estado actual de Carter vs. estándar 2026

| Dimensión | Carter hoy | Estándar 2026 | Gap |
|-----------|-----------|--------------|-----|
| Verificación de acciones | ✅ VerificationManager por tool | Screenshot + visual | Carter ya está adelante |
| Sin fake success | ✅ fake_success_guard | Nadie más lo tiene | Carter ya está adelante |
| Sin hardcodes | ✅ hardcode_guard | Nadie más lo tiene | Carter ya está adelante |
| Control GUI | ⚠️ Screenshot + OCR | Accessibility Tree (UIA) | Carter está atrás |
| Progreso en misiones | ❌ Silencio total | Async stream de eventos | Carter está atrás |
| Memoria entre sesiones | ⚠️ Solo MemoryStore básico | Narrative + Episodic Memory | Carter está atrás |
| Planificación jerárquica | ⚠️ step_budget=6 plano | Manager + Subtasks | Carter está atrás |
| Voz | ❌ No implementada | STT+TTS local | Carter está atrás |
| Selección de modelo por hardware | ❌ Manual | Auto-detección VRAM | Carter está atrás |

---

## Qué absorber y de quién

### CRÍTICO 1 — Accessibility Tree en vez de screenshots
**Fuente:** Windows-Use + Agent-S  
**Problema que resuelve:** Carter usa screenshots + OCR para verificar acciones GUI. Es lento, frágil y falla si la ventana está tapada o minimizada.  
**Solución:** Windows UI Automation (UIA) — lee el árbol de elementos de cualquier app como texto estructurado.

**Por qué es mejor:**
- Determinista: los elementos tienen nombres, no coordenadas de píxel
- Funciona con ventanas minimizadas, tapadas, fuera de pantalla
- Más rápido: texto << screenshot para el LLM
- Verifica post-acción leyendo el árbol de nuevo (estado cambió = acción confirmada)

**Cómo implementar en Carter (sin violar ContextoCarter.md):**
```python
# Librería: pywinauto (ya está en requirements de Carter)
from pywinauto.application import Application

class UIAVerifier:
    """Reemplaza screenshot para verificación de acciones GUI"""
    
    def read_app_tree(self, app_name: str) -> dict:
        app = Application(backend="uia").connect(title_re=f".*{app_name}.*")
        elements = []
        for el in app.top_window().iter_children():
            elements.append({
                "id": len(elements),
                "name": el.window_text(),
                "role": el.element_info.control_type,
                "visible": el.is_visible(),
                "enabled": el.is_enabled(),
            })
        return {"elements": elements}
    
    def state_changed(self, before: dict, after: dict) -> bool:
        """Verifica que algo cambió después de la acción"""
        return before != after
```

**Impacto en VerificationManager:** `app_open` y `window_action` verifiers pueden usar UIA en vez de process list + screenshot. Más preciso, más rápido.

**Librería recomendada:** `pywinauto` (ya está instalada en Carter) con backend `uia`  
**Alternativa más potente:** `uiautomation` (github.com/yinkaisheng/Python-UIAutomation-for-Windows)

**Prioridad:** CRÍTICA | **Complejidad:** Media (2-3 semanas) | **Ganancia:** 5-10x más rápido en GUI

---

### CRÍTICO 2 — Árbol UIA aumentado con OCR (fallback para UIs custom)
**Fuente:** Agent-S (ICLR 2025 Best Paper)  
**Problema:** Algunas apps usan botones con solo íconos (sin texto). UIA no puede leerlos.  
**Solución:** UIA primero, OCR como fallback solo donde falte texto.

```
App UI
  ↓
UIA Tree (nombre, rol, estado, bounds) ← principal
  ↓ (si botón sin texto)
OCR sobre bounds del elemento ← fallback selectivo
  ↓
LLM recibe árbol completo con texto
```

**Ganancia:** Cobertura del 99% de apps Windows sin modelo de visión.

**Prioridad:** CRÍTICA | **Complejidad:** Simple (1 semana adicional) | **Ganancia:** 99% cobertura

---

### ALTA 1 — Progress reporting async en misiones compuestas
**Fuente:** Open Interpreter (stream_events pattern)  
**Problema:** Carter ejecuta misiones en silencio. El usuario no sabe si Carter está trabajando o colgado. Viola Valor 17 de ContextoCarter.md.  
**Solución:** Generador async que emite eventos semánticos durante la ejecución.

```python
# En AgentEngine — añadir generador de progreso
async def run_mission_streaming(self, mission: str):
    yield {"type": "started", "mission": mission}
    
    steps = self.decompose(mission)
    for i, step in enumerate(steps[:self.step_budget]):
        yield {
            "type": "step_started", 
            "index": i + 1, 
            "total": len(steps),
            "tool": step.tool_call.name
        }
        result = await self.execute_step(step)
        yield {
            "type": "step_completed",
            "tool": step.tool_call.name,
            "status": result.verifier_status
        }
    
    yield {"type": "mission_completed"}

# En CLI — mostrar progreso
async for event in agent.run_mission_streaming(user_input):
    if event["type"] == "step_started":
        print(f"[{event['index']}/{event['total']}] {event['tool']}...")
    elif event["type"] == "step_completed":
        print(f"✓ {event['tool']}: {event['status']}")
```

**Nota anti-hardcode:** Los mensajes de progreso vienen del nombre de la tool declarativa, no de strings hardcodeados por acción.

**Prioridad:** ALTA | **Complejidad:** Media (1 semana, refactor AgentEngine a async) | **Ganancia:** UX crítica para Valor 17

---

### ALTA 2 — Memoria narrativa + episódica (Agent-S pattern)
**Fuente:** Agent-S paper (arxiv 2410.08164, ICLR 2025)  
**Problema:** Carter olvida todo entre sesiones. Si el usuario pidió "abre Spotify y pon música" antes, Carter no recuerda cómo lo resolvió.  
**Solución:** Dos capas de memoria adicionales sobre el MemoryStore SQLite existente.

**Memoria Narrativa** (nivel de misión):
```python
# Guarda resúmenes de misiones completas exitosas
# "Para abrir Spotify y poner música: app_open('spotify') → 
#  esperar proceso → web_open_url('spotify:track:...')"
class NarrativeMemory:
    def store_mission(self, mission: str, steps: list[str], success: bool):
        summary = f"Para '{mission}': {' → '.join(steps)}"
        self.db.execute(
            "INSERT INTO narrative_memory (mission, summary, ts) VALUES (?,?,?)",
            (mission, summary, time.time())
        )
    
    def find_similar(self, new_mission: str) -> list[str]:
        # IntentClassifier encuentra misiones similares estructuralmente
        # Sin keywords — usa distancia estructural
        ...
```

**Memoria Episódica** (nivel de subtarea):
```python
# Guarda secuencias de acciones reutilizables
# "Para hacer login en cualquier web: 
#  find('email field') → type(email) → find('password') → type(pwd) → click('login')"
class EpisodicMemory:
    def store_subtask(self, subtask: str, actions: list[dict]):
        self.db.execute(
            "INSERT INTO episodic_memory (subtask, actions, ts) VALUES (?,?,?)",
            (subtask, json.dumps(actions), time.time())
        )
    
    def retrieve(self, subtask: str) -> list[dict] | None:
        # Si ya hicimos esto antes, reutilizar la secuencia
        ...
```

**Integración con Carter:** Ambas tablas van en el mismo SQLite del MemoryStore. No hay cloud. No hay servicio externo.

**Prioridad:** ALTA | **Complejidad:** Media (3 semanas) | **Ganancia:** 50% más rápido en tareas repetidas

---

### ALTA 3 — Self-Evaluator (¿el paso realmente funcionó?)
**Fuente:** Agent-S  
**Problema:** Carter detecta si una tool retornó error, pero no si el resultado fue el esperado semánticamente.  
**Solución:** Después de cada paso, preguntar al LLM (o al árbol UIA) "¿está el objetivo logrado?"

```python
# Post-step evaluation sin hardcodes
def evaluate_step(self, step_goal: str, tree_before: dict, tree_after: dict) -> bool:
    """Pide al LLM que evalúe si el paso logró su objetivo"""
    # El LLM compara el árbol antes/después y el objetivo
    # Sin keywords hardcodeados — el LLM razona sobre el árbol
    prompt = f"Goal: {step_goal}\nBefore: {tree_before}\nAfter: {tree_after}\nDid it succeed? yes/no"
    result = self.llm.ask(prompt, max_tokens=5)
    return "yes" in result.lower()
```

**Prioridad:** ALTA | **Complejidad:** Simple (1 semana) | **Ganancia:** Mejor detección de fallos silenciosos

---

### MEDIA 1 — Prompting VoT (Visualization-of-Thought)
**Fuente:** PyWinAssistant (paper arxiv 2404.03622)  
**Problema:** Los LLMs tienen dificultad con razonamiento espacial ("haz click en el botón a la derecha del campo de texto").  
**Solución:** Pedir al LLM que "visualice" el layout antes de actuar.

```python
# En turn_support.py — variante de prompt para acciones GUI
vot_prefix = (
    "Before selecting an action, describe what you 'see' in the UI tree: "
    "which elements are present, their spatial relationship, and their state. "
    "Then select the action."
)
```

**Ganancia:** Mejor precisión en casos borde sin modelo de visión.  
**Costo:** Aumenta latencia del LLM (~20% más tokens en el prompt).

**Prioridad:** MEDIA | **Complejidad:** Simple (3 días) | **Ganancia:** Edge cases GUI

---

### MEDIA 2 — Mecanismo de interrupción/cancelación de misión
**Fuente:** Open Interpreter  
**Problema:** Si Carter está ejecutando una misión larga y el usuario escribe "para" o "cancela", no hay forma de detenerlo.  
**Solución:** Canal de cancelación via asyncio Event.

```python
class AgentEngine:
    def __init__(self):
        self._cancel_event = asyncio.Event()
    
    async def run_mission(self, mission: str):
        for step in steps:
            if self._cancel_event.is_set():
                return MissionResult(status="cancelled")
            result = await self.execute_step(step)
    
    def cancel(self):
        """El usuario puede cancelar en cualquier momento"""
        self._cancel_event.set()
```

**Prioridad:** MEDIA | **Complejidad:** Simple (1 semana) | **Ganancia:** Control de usuario en misiones largas

---

## Fase de Voz — Cómo implementarla correctamente

### STT — faster-whisper (mejor opción 2026)
**¿Por qué no whisper.cpp?** faster-whisper es 4-6x más rápido en GPU. whisper.cpp es mejor solo en CPU-only.  
**¿Por qué no Piper TTS?** Piper fue archivado en octubre 2025. Ya no se mantiene.

```python
from faster_whisper import WhisperModel

# Carga una sola vez al iniciar Carter
stt = WhisperModel("base", device="cuda", compute_type="float16")
# VRAM: ~1.5 GB para base, ~2.5 GB para small

def transcribe(audio_bytes: bytes) -> str:
    segments, _ = stt.transcribe(audio_bytes)
    return "".join(seg.text for seg in segments)
```

**Modelos disponibles:** tiny (75M), base (145M), small (244M), medium (769M)  
**Recomendación para Carter:** `base` para hardware de 8-16GB (deja VRAM para el LLM principal)

### TTS — Kokoro (mejor opción 2026, Piper está archivado)

```python
from kokoro import KokoroTTS

tts = KokoroTTS(voice="af")  # af=American Female, am=Male, etc.
# Solo 82M parámetros, corre en CPU

def speak(text: str):
    audio = tts.synthesize(text)
    play_audio(audio)  # sounddevice o pyaudio
```

### Arquitectura de voz en Carter (como capa, no cerebro separado)

```
Audio capturado (push-to-talk o wake word)
    ↓
faster-whisper → texto
    ↓
[mismo AgentEngine que hoy] → respuesta texto
    ↓
Kokoro TTS → audio
    ↓
Reproducir por altavoces
```

**Importante:** La voz es solo entrada/salida. El núcleo Carter no cambia. Esto respeta Valor 26 de ContextoCarter.md exactamente.

---

## Fase de Selección Automática de Modelo

### VRAM detection en Python

```python
def detect_available_vram() -> float:
    """Retorna GB de VRAM disponible. 0 si solo CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory / 1e9
            reserved = torch.cuda.memory_reserved(0) / 1e9
            return max(0, total - reserved - 2.0)  # -2GB para overhead del sistema
    except ImportError:
        pass
    return 0.0

# Perfiles según Valor 8 de ContextoCarter.md
MODEL_PROFILES = {
    "cpu_only":  {"planning": "qwen2.5:1.5b",     "context": 2048},
    "6gb":       {"planning": "qwen2.5:3b-q4",    "context": 4096},
    "8gb":       {"planning": "qwen2.5:7b-q4",    "context": 4096},
    "10gb":      {"planning": "mistral:7b-q4",    "context": 8192},
    "12gb":      {"planning": "llama3.1:8b-q4",   "context": 8192},
    "16gb":      {"planning": "llama3.1:8b",      "context": 8192},
    "24gb":      {"planning": "qwen2.5:14b",      "context": 16384},
}

def select_profile(vram_gb: float) -> dict:
    if vram_gb < 2:   return MODEL_PROFILES["cpu_only"]
    if vram_gb < 7:   return MODEL_PROFILES["6gb"]
    if vram_gb < 9:   return MODEL_PROFILES["8gb"]
    if vram_gb < 11:  return MODEL_PROFILES["10gb"]
    if vram_gb < 13:  return MODEL_PROFILES["12gb"]
    if vram_gb < 18:  return MODEL_PROFILES["16gb"]
    return MODEL_PROFILES["24gb"]
```

**Integración:** En `run_carter_v3.ps1` y `Run_Carterv3.py`, detectar VRAM antes de iniciar el launcher y pasar el modelo como variable de entorno.

---

## Fase de Visión — Cuándo y cómo

### Recomendación: NO usar visión como capa principal

El árbol UIA + OCR de fallback cubre el 99% de casos sin necesitar un VLM. La visión solo tiene sentido para:
- "¿Qué ves en pantalla?" (usuario pide descripción visual)
- Apps con UI completamente custom sin UIA (raro)
- Screenshots como evidencia visual

### Si se necesita VLM local (hardware ≥ 16GB VRAM)

| Modelo | Tamaño | 8GB? | 16GB? | Calidad |
|--------|--------|------|-------|---------|
| moondream2 | 829MB | ✅ | ✅ | 6/10 |
| MiniCPM-V 2.6 | 5.5GB (int4) | ⚠️ justo | ✅ | 8/10 |
| LLaVA-1.5-7B | 4GB (q4) | ⚠️ justo | ✅ | 7/10 |

**Recomendación para Carter:** moondream2 como fallback visual cuando UIA falla. No como capa principal.

---

## Roadmap priorizado completo

### Fase A — Post-validación live (hacer primero)
*Prerequisito: Carter pasa el spotcheck live con Ollama real*

| Semana | Tarea | Fuente | Prioridad |
|--------|-------|--------|-----------|
| 1-2 | Reemplazar screenshot con UIA tree en verifiers | Windows-Use | CRÍTICA |
| 3 | OCR fallback para botones sin texto en UIA | Agent-S | CRÍTICA |
| 4 | Async progress events en AgentEngine | Open Interpreter | ALTA |

### Fase B — GUI y Planificación
| Semana | Tarea | Fuente | Prioridad |
|--------|-------|--------|-----------|
| 5-6 | Narrative Memory (resúmenes de misiones) | Agent-S | ALTA |
| 7-8 | Episodic Memory (secuencias reutilizables) | Agent-S | ALTA |
| 9 | Self-Evaluator post-paso | Agent-S | ALTA |
| 10 | Cancel/interrupt de misión | Open Interpreter | MEDIA |

### Fase C — Voz (siguiente fase grande)
| Semana | Tarea | Stack | Prioridad |
|--------|-------|-------|-----------|
| 11 | STT local con faster-whisper | faster-whisper | MEDIA |
| 12 | TTS local con Kokoro | Kokoro | MEDIA |
| 13 | Loop voz→texto→Carter→texto→voz | Integración | MEDIA |
| 14 | Push-to-talk en launcher | Windows audio | MEDIA |

### Fase D — Hardware Inteligente
| Semana | Tarea | Stack | Prioridad |
|--------|-------|-------|-----------|
| 15 | Detección de VRAM al arranque | torch.cuda | MEDIA |
| 16 | Selección automática de modelo según perfil | OllamaAdapter | MEDIA |

### Fase E — Visión (cuando hardware lo permita)
| Semana | Tarea | Stack | Prioridad |
|--------|-------|-------|-----------|
| 17+ | moondream2 como fallback visual | transformers | BAJA |

---

## Lo que NO absorber (razones)

| Proyecto | Patrón | Por qué NO |
|---------|--------|-----------|
| Mark XXXIX | Gemini API para visión | Cloud obligatoria — viola privacidad local |
| Open Interpreter | Ejecución de código libre | Carter usa tools declarativas — más seguro y verificable |
| OpenClaw | Multi-canal (WhatsApp/Telegram) | Mensajes pasan por terceros — viola privacidad |
| Agent-S | Vision-only GUI (sin UIA) | UIA es mejor en Windows — más rápido y determinista |

---

## Resultado esperado después de absorción completa

Carter v3 post-absorción vs. competidores:

| Dimensión | Carter v3.1 | Open Interpreter | Agent-S | Mark XXXIX |
|-----------|------------|-----------------|---------|-----------|
| 100% local | ✅ | ✅ | ✅ | ❌ Google |
| Windows nativo | ✅ | ⚠️ WSL | ✅ | ✅ |
| Anti-fake-success | ✅ | ❌ | ❌ | ❌ |
| Accessibility Tree | ✅ | ❌ screenshot | ✅ | ❌ vision |
| Narrative Memory | ✅ | ❌ | ✅ | ❌ |
| Progreso en misiones | ✅ | ✅ | ⚠️ | ⚠️ |
| Voz local | ✅ | ✅ (01 App) | ❌ | ✅ |
| Selección de modelo por VRAM | ✅ | ❌ | ❌ | ❌ |
| Sin hardcodes (auditado) | ✅ | ❌ | ❌ | ❌ |

**Conclusión:** Carter v3 post-absorción tiene una combinación única que ningún competidor tiene completa: local + verificado + sin fake success + UIA + memoria + voz + hardware-aware.

---

*Auditoría realizada 2026-05-06 por Claude Code sobre código real de 6 proyectos competidores*  
*Fuentes: Open Interpreter, Agent-S (arXiv 2410.08164), Windows-Use, PyWinAssistant, DirectShell, Mark XXXIX*
