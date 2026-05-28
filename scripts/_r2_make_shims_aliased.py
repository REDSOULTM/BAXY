"""R2 sprint 2026-05-28: hacer los shims `domain_tools_X.py` ALIASES del
módulo real `domain_tools.X` via `sys.modules` aliasing.

El intento anterior copiaba atributos (shim transparente al lectura),
pero `mock.patch.object(shim, "X")` mockea sobre el SHIM, mientras el
código de producción adentro de `domain_tools.X` busca `X` en su PROPIO
namespace (el módulo real). Los mocks viejos no llegaban al sitio real.

Fix: alias-via-sys.modules. Cuando alguien importa
`gemma4_agent.domain_tools_X`, devolvemos el MISMO objeto-módulo que
`gemma4_agent.domain_tools.X`. Cualquier mock o patch llega al sitio
real porque ES el sitio real.
"""
from __future__ import annotations

import sys
from pathlib import Path


SHIM_TEMPLATE = '''"""Back-compat shim — `gemma4_agent.domain_tools_{area}` es un ALIAS
exacto de `gemma4_agent.domain_tools.{area}` (mismo objeto-módulo via
sys.modules). Mocks viejos siguen funcionando porque el patch llega al
mismo namespace que ejecuta el código.

R2-finalize sprint 2026-05-28.
"""
import sys as _sys
from .domain_tools import {area} as _real

# Mismo objeto módulo: cualquier mock.patch.object(this, X) toca el real.
_sys.modules[__name__] = _real
'''


def main() -> int:
    pkg = Path("gemma4_agent")
    shims = sorted(pkg.glob("domain_tools_*.py"))
    print(f"Found {len(shims)} shims.")
    for sib in shims:
        area = sib.stem.replace("domain_tools_", "")
        sib.write_text(SHIM_TEMPLATE.format(area=area), encoding="utf-8")
    print(f"Done. {len(shims)} shims aliased via sys.modules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
