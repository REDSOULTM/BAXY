# Carter v2 — Sesión 11: Bug fixes basados en resultados del probe S10

## Contexto

Carter es un asistente de Windows con LLM (Qwen3-8B vía Ollama) que ejecuta herramientas reales.
La sesión 10 corrió un probe exhaustivo de todas las tools y documentó fallos en `probe_session10_results.json`.
Esta sesión arregla **exactamente** los fallos documentados — nada más.

**Repo:** `Carter_v2/`
**Rama activa:** `rebuild/v2-from-scratch`

---

## Primer paso obligatorio — leer los resultados

Antes de tocar código, leer `Carter_v2/probe_session10_results.json` completo.

El JSON tiene esta estructura:
```json
{
  "timestamp": "...",
  "total": 90,
  "passed": 85,
  "failed": 4,
  "skipped": 1,
  "failures": [
    {
      "id": "EMAIL-1",
      "desc": "...",
      "input": "...",
      "tools_called": ["notify_toast"],
      "reply": "...",
      "reason": "LLM llamó notify_toast en vez de email_send",
      "failure_type": "ROUTING"
    }
  ]
}
```

Clasificar cada fallo antes de arreglarlo:

| Tipo | Causa | Fix |
|------|-------|-----|
| `ROUTING` | LLM eligió tool equivocada | Mejorar description/compact_description en `tools.py` |
| `CRASH` | Tool lanzó excepción | Arreglar bug en la capability |
| `WRONG_OUTPUT` | Tool corrió pero devolvió datos incorrectos | Arreglar lógica de la capability |
| `NO_TOOL` | LLM no usó ninguna tool | Mejorar description o añadir a compact catalog |

---

## Estrategia de fixes por tipo

### ROUTING — Fix en `adapters/tools.py`

El LLM eligió una tool similar pero incorrecta. El 90% de los routing failures se arreglan con:

1. **Mejorar `compact_description`** — debe ser inequívoca y distinguirse claramente de tools similares.
   ```python
   # MAL — ambiguo:
   "email_send": "Send an email message."
   # BIEN — específico:
   "email_send": "Send email via Outlook or SMTP. Use ONLY for email, not notifications."
   ```

2. **Sacar de `_COMPACT_DEPRECATED_TOOL_NAMES`** si la tool estaba oculta al LLM.
   ```python
   # Verificar que el nombre NO esté en este set
   _COMPACT_DEPRECATED_TOOL_NAMES: set[str] = { ... }
   ```

3. **Mejorar `description` completa** con ejemplos de cuándo usar y cuándo NO usar:
   ```python
   description=(
       "Send an email to one or more recipients. Use this when the user says 'send email', "
       "'write an email', 'email to X'. Do NOT use for toast notifications or reminders."
   )
   ```

4. **Añadir `failure_chain`** si la tool puede fallar y hay alternativa:
   ```python
   failure_chain=[
       "try terminal_run_powershell with Send-MailMessage if SMTP not configured",
   ]
   ```

### CRASH — Fix en la capability correspondiente

Leer el traceback completo del JSON. Patrones comunes:

**ImportError de dependencia opcional:**
```python
# MAL:
import pypdf  # lanza ImportError si no está instalado

# BIEN:
try:
    import pypdf
except ImportError:
    return CapabilityResult(False, "pypdf not installed.",
        next_step_hint="pip install pypdf")
```

**FileNotFoundError en path:**
```python
# Siempre validar que el path existe antes de abrir
from pathlib import Path
p = Path(path)
if not p.exists():
    return CapabilityResult(False, f"File not found: {path}", errors=[f"{path} does not exist"])
```

**Timeout en subprocess:**
```python
# Usar run_with_kill con timeout explícito
from ._subprocess import run_with_kill
rc, stdout, stderr = run_with_kill(["ffmpeg", "-i", input, output], timeout=60)
if rc != 0:
    return CapabilityResult(False, f"ffmpeg failed: {stderr[:200]}", errors=[stderr])
```

**COM/win32 exception:**
```python
# Siempre envolver COM en try/except con mensaje claro
try:
    app = win32com.client.Dispatch("Outlook.Application")
except Exception as exc:
    return CapabilityResult(False, f"Outlook not available: {exc}",
        next_step_hint="Install Outlook or configure SMTP via CARTER_EMAIL_* env vars")
```

### WRONG_OUTPUT — Fix en la capability

La tool corrió pero devolvió datos mal estructurados. Verificar:

1. `data` dict tiene las keys que el LLM espera (`text`, `pages`, `results`, etc.)
2. Valores no son `None` cuando se espera string/list
3. Encoding correcto (UTF-8, no latin-1)
4. Listas no vacías cuando debería haber datos

### NO_TOOL — Fix en `tools.py`

El LLM no usó ninguna tool cuando debería haberlo hecho. Causas:

1. Tool en `_COMPACT_DEPRECATED_TOOL_NAMES` → sacarla
2. `compact_description` no describe bien el trigger de la tool
3. Tool no tiene entrada en `_COMPACT_DESCRIPTIONS` → añadirla

---

## Patrones de code a respetar

### Capability — estructura base
```python
from __future__ import annotations
from ..types import CapabilityRequest, CapabilityResult
from .base import Capability

class XyzCapability(Capability):
    namespace = "xyz"

    def supports(self, action: str) -> bool:
        return action in {"action_a", "action_b"}

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        p = request.params
        if request.action == "action_a":
            return _action_a(str(p.get("param") or ""))
        raise ValueError(f"Unsupported action: {request.action}")
```

### CapabilityResult correcta
```python
# OK con datos
CapabilityResult(True, "Mensaje corto para el LLM.", data={"key": "value"})

# Error con hint
CapabilityResult(False, "Qué falló.", errors=["detalle técnico"], next_step_hint="qué hacer")
```

### Subproceso con timeout
```python
from ._subprocess import run_with_kill
rc, stdout, stderr = run_with_kill(["programa", "arg1"], timeout=30)
```

---

## Verificación de fixes

Después de cada fix, re-correr **solo los tests fallidos** del probe:

```bash
cd Carter_v2
# Re-correr probe solo con los IDs fallidos (añadir flag --only al probe si no existe)
python probe_all_tools.py --only EMAIL-1,PDF-3,NETX-2
```

Si el probe no tiene flag `--only`, añadirlo:

```python
# En probe_all_tools.py, al inicio del runner:
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--only", default="", help="Comma-separated test IDs to run")
args = parser.parse_args()
only_ids = set(args.only.split(",")) if args.only else set()

# En el bucle:
if only_ids and test["id"] not in only_ids:
    continue
```

---

## Verificación final

Al terminar todos los fixes:

1. Correr el probe completo:
```bash
python probe_all_tools.py
```

2. Correr la suite de tests:
```bash
cd Carter_v2
pytest tests/ -v
```

3. El objetivo es:
   - **probe:** pasar todos los tests que fallaron en S10 (los que eran SKIP por falta de dependencia pueden seguir en SKIP)
   - **pytest:** 0 regresiones — todos los tests que pasaban en S9 siguen pasando

4. Guardar resultados en `probe_session11_results.json` con el mismo formato que S10.

5. Hacer commit con mensaje: `fix(s11): resolve all s10 probe failures`.

---

## Reglas

1. **Solo arreglar lo que falló** — no refactorizar, no añadir features, no limpiar código.
2. **Un fix por fallo** — si un fix arregla varios fallos, documentarlo.
3. **No cambiar interfaces** — los nombres de tools, parámetros y namespaces no cambian.
4. **Tests primero** — si un CRASH tiene test unitario que lo reproduce, arreglarlo en el test antes que en el código.
5. Si un fallo no se puede arreglar sin dependencia externa (ej. Outlook no instalado), documentarlo en el JSON de resultados como `SKIP_EXTERNAL` con explicación — no es un bug.
