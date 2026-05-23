# Para el agente Carter — Aplicar la separación de prompts que se hizo acá

**Origen:** repo `Probando Gemma 4` (donde Gemma 4 sacó **540/540 = 100%**).
**Destino:** repo `Carter OS AI`.
**Mensaje del humano:** "qwen debe tener su propio system prompt totalmente por separado al igual que gemma4".
**Fecha:** 2026-05-11.

---

## TL;DR (lo que tenés que hacer, sin ambigüedad)

En este repo, el bench Carter 540 sacó **540/540 con Gemma 4 E4B-Q6_K**. NO usé un system prompt genérico — usé uno **diseñado específicamente para Gemma 4** (`harness_carter540/system_prompt.py` v3, 143 líneas, 14 iteraciones).

En tu repo, vos tenés un único `CORE_PROMPT` (presumiblemente tunneado para qwen3:4b cuando empezó Carter) y lo estás reutilizando con Gemma 4 vía `CARTER_LLM_BACKEND=llama-server`. **Eso explica las "respuestas horribles"** que reportaste en el `INFORME_NOCTURNO` (saludos concatenados, placeholder "(acción ejecutada)", loop depth>3, etc.).

**La instrucción concreta:** separá los system prompts por backend. Cada modelo tiene los suyos. Sin if-elif tampoco — declarativo.

---

## Por qué importa (no es opinión, es evidencia medida)

| Modelo | Sampling oficial | Tokens especiales | DPO/RLHF target |
|---|---|---|---|
| **qwen3:4b-instruct-2507-q4_K_M** | T=0.7, top_p=0.8, top_k=20 | `<\|im_start\|>` `<\|im_end\|>` | Instruction-following sobrio |
| **gemma-4-E4B-it-Q6_K** | T=1.0, top_p=0.95, top_k=64 | `<\|turn\|>` `<\|tool_call\|>` `<\|think\|>` | RLHF rioplatense + agentic |

**No son intercambiables a nivel prompt.** Específicamente:
- Gemma 4 entrenado para T=1.0 — **bajar a 0.7 (qwen default) degrada**, no mejora. Verificado en mi bench v6 (Decisión 4 en [documentacion/09_arquitectura_decisiones/README.md](documentacion/09_arquitectura_decisiones/README.md)).
- Gemma 4 tiene parser nativo de tool_call (PR #21418 mergeado). Si el prompt instruye "escribí JSON entre triple backticks" — qwen entiende, Gemma 4 lo da en su formato nativo y el parser de qwen no lo levanta.
- Gemma 4 hace thinking implícito que el parser strippea automáticamente. Si el prompt incluye anti-thinking instructions, regresiona (medido v13 → -1.5pp).

---

## Lo que hice acá (replicalo en tu repo)

### 1. Estructura de archivos

En tu repo, en lugar de un `CORE_PROMPT` único:

```
Carter_v4/
├── prompts/
│   ├── __init__.py
│   ├── qwen3_4b_prompt.py        ← el system_prompt original que ya tenías
│   └── gemma4_e4b_prompt.py      ← copia EXACTA de mi system_prompt.py v3
└── core/
    └── prompt_loader.py          ← elige según CARTER_LLM_BACKEND
```

### 2. El prompt de Gemma 4 que tenés que copiar TAL CUAL

Tomá el archivo entero:

**Origen:** `C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\harness_carter540\system_prompt.py`
**Destino:** `C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\Carter_v4\prompts\gemma4_e4b_prompt.py`

**No lo edites.** Es el prompt que sacó **540/540** después de 14 iteraciones documentadas en [documentacion/03_iteraciones_540/README.md](documentacion/03_iteraciones_540/README.md). Cada regla tiene una causa raíz medida.

Reglas críticas que NO podés tocar (resumen — el archivo completo tiene 143 líneas con anti-examples):

| Regla | Por qué existe |
|---|---|
| `R1 HONESTY` con excepción para "general knowledge" | v8 falló C16 "quién es Spider-Man" porque el modelo decía "no lo sé" (overcorrected sobre R1) |
| `R2 ONE-SHOT TOOL CALL PER TURN` | v9 chainaba tools en multi-step y rompía verifiers |
| `R3 NEGATION` con lista explícita | Patrón L del audit Carter, v3 detectó que regex no alcanza |
| `R4 DESTRUCTIVE` con whitelist explícita de NOT-destructive | v11 marcaba `echo` como destructivo (← exactamente tu C11-01 bug actual) |
| Camera/mic/banking en lista destructive | Valor 15 + Valor 4 ContextoCarter |
| Anti-thinking-tags rule | Algunos parsers leakean `<\|channel\|>`, mi build b9090 los strippea pero el prompt lo refuerza |
| "Speak Rioplatense Spanish... Reason silently in English" | v5 detectó que Gemma 4 razona mejor en EN pero el usuario quiere reply en ES |

### 3. El loader

```python
# Carter_v4/core/prompt_loader.py
"""Selecciona el system prompt según el backend LLM activo.

Cada modelo tiene su propio prompt tunneado. NO compartir prompts entre
modelos — sampling oficial, tokens especiales y RLHF targets difieren.
"""
import os
from Carter_v4.prompts.qwen3_4b_prompt import SYSTEM_PROMPT as QWEN_PROMPT
from Carter_v4.prompts.gemma4_e4b_prompt import SYSTEM_PROMPT as GEMMA4_PROMPT


def get_system_prompt(backend: str | None = None) -> str:
    """Devuelve el system prompt del backend activo.

    Args:
        backend: 'ollama' | 'llama-server' | None (lee env).
    """
    backend = backend or os.environ.get("CARTER_LLM_BACKEND", "ollama")
    if backend == "llama-server":
        return GEMMA4_PROMPT
    if backend == "ollama":
        return QWEN_PROMPT
    raise ValueError(f"Backend desconocido: {backend!r}")
```

### 4. Wire en el agent

Donde sea que `Agent.__init__` o el chat loop construya el system message, reemplazar:

```python
# ANTES
messages = [{"role": "system", "content": CORE_PROMPT}, ...]

# DESPUÉS
from Carter_v4.core.prompt_loader import get_system_prompt
messages = [{"role": "system", "content": get_system_prompt()}, ...]
```

### 5. Sampling también separado (ya lo tenés en el adapter, verificalo)

Tu adapter llama-server (commit `c91ceb46`) ya manda T=1.0 etc. Confirmá que cuando `CARTER_LLM_BACKEND=ollama` mande el sampling de qwen (T=0.7, top_p=0.8, top_k=20), no los de Gemma 4. Si los mezclaste, qwen va a degradar.

---

## Cómo verificar que funcionó (antes de gastar 2h en el bench 540 full)

**Test rápido — 30 minutos:**

```powershell
# 1. Llamada directa a llama-server con el system_prompt de Gemma 4
$prompt = Get-Content "Carter_v4\prompts\gemma4_e4b_prompt.py" | Out-String
# (copiar el SYSTEM_PROMPT manualmente o cargarlo en Python)

# 2. Levantar mi chat_carter.py de este repo apuntando al mismo llama-server
cd "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"
python chat_carter.py
# Probar:
#   "abre Steam"               → debe llamar app_open(name="Steam"), reply 1 línea
#   "ejecuta echo CarterOK"    → debe llamar terminal_run, NO rechazar
#   "abre Steam si está instalado" → debe verificar primero, no destructive
#   "abre stean" (typo)        → debe llamar app_open(name="stean") sin loop
#   "quién eres"               → reply corto, NO concatenar saludos
```

Si esos 5 casos andan bien con `chat_carter.py` (mi script crudo, sin agent loop de Carter), entonces:
- Confirmaste que Gemma 4 + mi prompt + llama-server es OK.
- Las regresiones del INFORME_NOCTURNO son **del wrapper de Carter**, no del modelo.

**Test largo — re-correr bench 540:**
Solo con confianza tras el test rápido. Comando que ya tenés en INFORME_NOCTURNO sección "Siguiente acción humana sugerida".

---

## Hallazgos del INFORME_NOCTURNO mapeados a causas

| Caso INFORME | Causa probable | Fix |
|---|---|---|
| C09-01 saludo concatenado | `CORE_PROMPT` qwen instruye saludar | Prompt Gemma 4 no saluda — usar el mío |
| C11-01 echo rechazado | `detect_destructive_intent` muy agresivo o prompt sin whitelist | Mi R4 tiene whitelist explícita: `echo/ls/dir/git_status/python --version` |
| C13-01 ventana activa alucinada | Stub o prompt no tiene `gui` consolidated correcto | Ver mi `tool_schemas_consolidated.json` |
| C14-01 `instal` regex bug | Bug de Carter, ya cerrado en `a830f369` | OK |
| C16-01 typo "stean" loop depth>3 | Agent loop de Carter, no LLM | Mi `chat_carter.py` lo resuelve sin loop |
| C17-01 "(acción ejecutada)" placeholder | Wrapper de Carter genera ese reply, no el modelo | Reemplazar por el `assistant.content` real del modelo |
| C18-01 saludo cuando no hay saludo | Mismo que C09-01 | Mismo fix |

**De 7 problemas reportados, 5 son de wrapper/prompt no separado, 1 es bug Carter ya cerrado, 1 (C13) requiere validar tool schema.**

---

## Lo que NO tenés que hacer

1. **NO reescribas el `system_prompt.py` de Gemma 4 con tu estilo.** Es producto de 14 iteraciones medidas. Cada regla tiene un fail anterior que la justifica.
2. **NO uses if-elif por modelo dentro del prompt** ("if model == gemma4: ..."). Eso viola tu propia regla "sin hacks por app". Separar archivos es declarativo.
3. **NO agregues más reglas a mi prompt** sin medir antes. v13 agregó `--reasoning off` + content stripping y regresionó -1.5pp.
4. **NO bajes T=1.0.** Lo verifiqué — degrada.

---

## Qué ganás con esto (predicción)

Mi bench 540 oficial sacó:
- **540/540 = 100%** con Gemma 4 E4B-Q6_K + system_prompt v3 + tools individuales
- **540/540** con tools consolidated 16 (tras v6 iteration)

Tu bench 540 con prompt separado + sampling correcto debería **subir del ~94% reportado a ~99%**. El 1% restante puede venir del wrapper de Carter (verifiers, agent loop) que mi bench no ejercita.

Si no sube ahí, quedan dos hipótesis:
- Tu `full_matrix_runner.py` mide cosas distintas a mi auditor v7 (estructural vs semántico — ya lo dijiste vos)
- Tus stubs/dispatcher de Carter difieren de los míos en firmas

Para ese caso: el archivo `harness_carter540/auditor.py` v7 está disponible para que copies los patrones de PASS/FAIL si querés alinear.

---

## Archivos a copiar literalmente

```
ORIGEN (este repo)                                    DESTINO (Carter OS AI)
────────────────────────────────────────              ────────────────────────────────────────
harness_carter540/system_prompt.py            →       Carter_v4/prompts/gemma4_e4b_prompt.py
harness_carter540/auditor.py                  →       Carter_v4/audit/auditor_gemma4.py (referencia, opcional)
harness_carter540/tool_schemas_consolidated.json  →   Carter_v4/tools/schemas_consolidated.json (ya lo tenés)
```

Para tu prompt de qwen — **mantenelo donde está**, solo movelo a `Carter_v4/prompts/qwen3_4b_prompt.py` para simetría.

---

## Resumen de la instrucción

> **"qwen debe tener su propio system prompt totalmente por separado al igual que gemma4"**

Implementación:
1. Crear `Carter_v4/prompts/qwen3_4b_prompt.py` (mover el actual)
2. Crear `Carter_v4/prompts/gemma4_e4b_prompt.py` (copiar de este repo, sin editar)
3. Crear `Carter_v4/core/prompt_loader.py` que selecciona según `CARTER_LLM_BACKEND`
4. Wire en `Agent.__init__` y cualquier otro lugar que arme el system message
5. Verificar sampling también está separado por backend en el adapter
6. Test rápido con 5 casos via `chat_carter.py` antes del bench full
7. Solo después correr bench 540

Tiempo estimado: **45 min código + 30 min validación + 2h bench = 3h 15min para confirmar 540/540 en Carter producción.**
