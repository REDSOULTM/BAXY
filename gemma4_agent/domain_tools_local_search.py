"""Back-compat shim — `gemma4_agent.domain_tools_local_search` es un ALIAS
exacto de `gemma4_agent.domain_tools.local_search` (mismo objeto-módulo via
sys.modules). Mocks viejos siguen funcionando porque el patch llega al
mismo namespace que ejecuta el código.

R2-finalize sprint 2026-05-28.
"""
import sys as _sys
from .domain_tools import local_search as _real

# Mismo objeto módulo: cualquier mock.patch.object(this, X) toca el real.
_sys.modules[__name__] = _real
