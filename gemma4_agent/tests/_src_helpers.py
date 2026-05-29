"""Lectura ROBUSTA de source de métodos de agent.py para los tests de
presencia-en-código.

Reemplaza `inspect.getsource(Gemma4Agent.<método>)`, que flakeaba intermitentemente
(~1/6 runs en suite full): cuando un test previo corrompía el import/sys.modules del
módulo agent (p.ej. fakes de sys.modules['sentence_transformers'] o importlib.reload),
un re-import parcial hacía que getsource devolviera la fuente EQUIVOCADA y el assertIn
fallara (AssertionError) — pero solo según el orden, de ahí la intermitencia. Pasaban
aislados.

Leer el ARCHIVO .py de disco es INMUNE a cualquier estado runtime (mock-patches,
sys.modules, reload, linecache). Es el MISMO patrón que test_audit_metrics.py /
test_audit_8r_verification.py (que ya leen agent.py de disco). Mantiene la precisión
por-método (slice del bloque `def` hasta el siguiente `def`/`class`).

NB: este archivo NO matchea el patrón de descubrimiento de pytest (test_*.py), así que
no se colecta como tests — es solo un helper.
"""
import re
from pathlib import Path


def agent_module_text() -> str:
    """Texto completo de agent.py leído del archivo (robusto)."""
    from gemma4_agent.agent_core import agent as _agent_mod
    return Path(_agent_mod.__file__).read_text(encoding="utf-8", errors="replace")


def agent_method_src(method_name: str) -> str:
    """Source del método `method_name` de agent.py, leído del ARCHIVO. Slice del bloque
    `    def <name>(` hasta el siguiente `    def `/`class `/EOF. '' si no se encuentra
    (el assertIn del test fallará, señalando un cambio real)."""
    text = agent_module_text()
    m = re.search(
        rf"\n(    (?:async )?def {re.escape(method_name)}\(.*?)"
        rf"(?=\n    (?:async )?def |\nclass |\Z)",
        text, re.S)
    return m.group(1) if m else ""
