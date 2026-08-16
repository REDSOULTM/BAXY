# COMPETITOR_AGENTS_DEEP_AUDIT.md
# Auditoría profunda de Agent-S (S3) — código real Python
# Generado por: GitHub Copilot (Claude) — 2026-05-06
# Ubicación: `Extras/Competidores/Agent-S-main/`

---

## ¿Por qué un deep audit de Agent-S?

Agent-S3 es **SOTA en OSWorld con 72.60%** (supera a humanos en algunos splits). Es el **único competidor con un verifier visual real (BBON)**: marca screenshots before/after y pide al LLM que confirme el cambio. Si Carter quiere una capa adicional de honestidad sobre acciones GUI, este es el patrón de referencia.

---

## 1. Estructura

- Lenguaje: **Python 3.10+**.
- Carpeta principal: `gui_agents/s3/`.
- Subcarpetas:
  - `agent_s.py` — entry point.
  - `agents/worker.py` — el ejecutor.
  - `bbon/` — Best-of-N: `behavior_narrator.py`, `comparative_judge.py`.
  - `core/engine.py` — abstracción multi-LLM (`LMMEngineOpenAI`, `LMMEngineAnthropic`, etc.).
  - `memory/procedural_memory.py` — system prompts estáticos.
  - `osworld_setup/s3/` — runners de evaluación.
  - `utils/common_utils.py` — utilidades (incluye `split_thinking_response`).

## 2. Loop principal

`AgentS3.predict()` en `gui_agents/s3/agent_s.py:84-90` → `Worker.generate_next_action()`.

`Worker.generate_next_action()`:

1. **Reflection agent (opcional)**: si `turn_count >= 1`, observa el historial + screenshot anterior y genera un resumen "qué pasó y por qué" (`agents/worker.py:115-160`).
2. **Generator agent (LLM)**: produce código `pyautogui` ejecutable.
3. **`BehaviorNarrator.judge()`** post-acción (ver §5).
4. Retorna acciones + info.

NO hay manager/planner explícito. El Worker es ejecutor directo (think-act-observe).

Loop control en `osworld_setup/s3/run_local.py`:

```python
while not done and step_idx < max_steps:  # lib_run_single.py:36
    response, actions = agent.predict(instruction, obs)
```

| Parámetro | Default | Archivo |
|---|---|---|
| `max_steps` | 15 | `run_local.py:95` |
| `max_trajectory_length` | 8 | `run_local.py:98` |
| Code agent budget | 20 | `memory/procedural_memory.py:51` |

## 3. Multi-LLM (`LMMEngine*`)

`gui_agents/s3/core/engine.py`:

- `LMMEngineOpenAI` (`:25-63`)
- `LMMEngineAnthropic` con **Claude thinking mode** budget 4096 tokens (`:66-120`, `:109-115`).
- `LMMEngineGemini` (`:150-200`).
- HuggingFace, vLLM, OpenRouter, Azure OpenAI.

Soporta exponential backoff automático.

`split_thinking_response()` en `utils/common_utils.py:158` extrae `<thoughts>` y `<answer>` del output de Claude thinking.

## 4. Acciones (pyautogui + grounding especial)

Acciones soportadas:

```python
pyautogui.click(x, y)
pyautogui.moveTo(x, y)
pyautogui.dragTo(x, y)
pyautogui.write('text')
pyautogui.press('key')
```

**Coordenadas absolutas** dependientes de la resolución del screenshot actual.

`create_pyautogui_code()` en `utils/common_utils.py:14` ejecuta el código directamente.

### Grounding especial: LibreOffice Calc

`grounding.py:79-200` define `SET_CELL_VALUES_CMD` que usa el **bridge UNO** de LibreOffice para set cell values **sin simular GUI** (acceso directo al modelo de la app).

> **Lección para Carter:** cuando una app expone una API (UNO, COM, AppleScript), usarla es 100x más fiable que click+screenshot.

### Code agent alternativo

`agent.call_code_agent()` (`memory/procedural_memory.py:37-39`) ejecuta Python/Bash en background. Step budget=20. Returns `DONE | FAIL | BUDGET_EXHAUSTED + summary`.

### Skipped por plataforma

`agents/worker.py:68-72`:

```python
if self.platform != "linux":
    skipped_actions = ["set_cell_values"]
```

## 5. **VERIFIER VISUAL (BBON) — LO MÁS IMPORTANTE**

### 5.1 BehaviorNarrator (`bbon/behavior_narrator.py`)

`:25-75`: marca la imagen *before* con anotaciones visuales de la acción (círculo/flecha sobre el click).

`:130-170`: pasa la imagen anotada *before* + imagen *after* a la LLM:

```python
def judge(self, screenshot_num, before_img, after_img, pyautogui_action):
    BehaviorNarrator.mark_action(mouse_actions, before_img)
    response = call_llm_formatted(self.judge_agent, ...)
    # Returns fact_thoughts + fact_answer
```

La LLM emite:
- `fact_thoughts`: razonamiento sobre el cambio observado.
- `fact_answer`: descripción factual ("la ventana de Steam se abrió", "no hubo cambio").

### 5.2 ComparativeJudge (`bbon/comparative_judge.py:100-145`)

Compara N rollouts (trajectorias) — ejecutadas en paralelo con seeds distintos — y elige la mejor visualmente:

```python
judge_choice = comparative_judge.select_best(
    initial_screenshot,
    [traj1_final, traj2_final, ...],
    [traj1_facts, traj2_facts, ...],
)
```

→ **Si todos los rollouts son malos, elige "el menos malo"** (limitación documentada).

### 5.3 Implicación

**No se puede declarar DONE sin evidencia visual.** Si el screenshot *after* no muestra el cambio esperado, el LLM lo reporta y el Worker reintentará.

**Carter actualmente** verifica estado lógico (procesos, ventanas, archivos, registry). Añadir BBON como capa opcional cuando hay VLM disponible eleva la honestidad de las acciones GUI al nivel de Agent-S.

## 6. Policy pre-LLM

**No engine.** Las restricciones viven en `memory/procedural_memory.py:25-70` (system prompt estático con guidelines: cuándo usar Code Agent vs GUI, qué tipos de tareas requieren verificación, cómo interpretar resultados del code agent).

→ Las restricciones son **prompt-level**, no enforced en código.

## 7. Memoria

**Sin persistencia entre sesiones.** Solo in-session:

```python
self.worker_history = []
self.reflections = []
self.screenshot_inputs = []
```
(`agents/worker.py:83-87`)

`PROCEDURAL_MEMORY` es un sistema **estático** de prompts (no aprendizaje).

Estrategia de flush (`worker.py:90-110`):
- Long-context models: mantiene últimas K imágenes.
- Modelos no-long-context: dropea turns enteros.

## 8. Hardcodes

**Mínimos** y todos justificados:

1. App detection vía fuzzy matching contra **window titles reales**:
   ```python
   closest_matches = difflib.get_close_matches('APP_NAME', window_titles, n=1, cutoff=0.1)
   # grounding.py:38
   ```
   → Cero hardcodes de apps.

2. LibreOffice defaults: `app_name="Untitled 1"`, `sheet_name="Sheet1"` (`grounding.py:90`) — pero se pasan como parámetros dinámicamente.

3. `skipped_actions` por plataforma (citado arriba).

→ **Filosofía idéntica a Carter**: cero hardcodes semánticos.

## 9. Tests

**Ningún test suite local.** La evaluación es OSWorld (set externo de 369 tasks reales).

Resultado: **Agent-S3 = 72.60%** (SOTA en OSWorld).

→ Carter tiene 490 tests con ScriptedAdapter pero ningún benchmark externo. Idea: adaptar OSWorld a Windows como benchmark.

## 10. Local-first

**Híbrido:**
- Ejecución (acciones GUI, screenshots, grounding): local.
- LLM: cloud por defecto (API keys de OpenAI/Anthropic). vLLM y Ollama posibles en teoría con `LMMEngine*` adecuado.

## 11. Lo mejor (real, citado)

1. **BBON con `BehaviorNarrator` + `ComparativeJudge`** — anti-fake-success por evidencia visual.
2. **`LMMEngine*`** — abstracción multi-proveedor limpia con thinking mode.
3. **Reflection agent** post-acción — analiza qué pasó antes de proponer la siguiente acción.
4. **Cero hardcodes de apps** — fuzzy contra window titles reales.
5. **UNO bridge para LibreOffice** — usa la API de la app cuando existe.
6. SOTA verificado externamente (72.60% OSWorld).

## 12. Lo peor (real, citado)

1. **Sin persistencia entre sesiones** — cada sesión empieza de cero.
2. **Hard requirement en imágenes** — VLM caro/lento sin GPU.
3. **BBON elige "el menos malo"** si todos los rollouts fallan.
4. **Cloud-dependent en la práctica** — vLLM/Ollama posibles pero no probados.
5. **Sin policy pre-LLM** — confía en el system prompt.

## 13. Qué portar a Carter (priorizado)

| # | Patrón Agent-S | Adaptación Carter | Prioridad |
|---|---|---|---|
| 1 | **Visual `BehaviorNarrator` opcional** | Verifier `visual_diff` que solo se activa si hay VLM (Ollama vision); para tools `verifier=async_visual` | **P1** |
| 2 | **Reflection agent** post-acción | Prompt opcional "antes de actuar, revisa qué falló en la última acción" cuando el verifier anterior fue UNVERIFIED/FAILED | **P2** |
| 3 | **`LMMEngine*` style abstraction** | Carter ya tiene `OllamaAdapter`; añadir adapters opcionales (Anthropic con thinking mode, OpenAI compat) con la misma interfaz | **P2** |
| 4 | **Best-of-N para acciones críticas** | Para tools `risk=CRITICAL` y `idempotent=True`, generar 2 rollouts y comparar | **P3** |
| 5 | **App API directa cuando exista** (UNO, COM, AppleScript) | Carter ya hace esto con WMI/win32api; documentar como pattern | **(ya implementado)** |
| 6 | **Adaptar OSWorld a Windows** como benchmark externo | Crear `audit/osworld_windows/` con 30-50 tasks reales | **P3** |

## 14. Lo que NO portar

- Sin persistencia entre sesiones: Carter ya tiene memoria SQLite, mejor patrón.
- Loop sin step budget enforced: Agent-S tiene `max_steps` pero no policy pre-LLM. Carter es superior aquí.
- VLM como único feedback: Carter verifica estado lógico (más rápido y barato), VLM debe ser capa opcional añadida.
