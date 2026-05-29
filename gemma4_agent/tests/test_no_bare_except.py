"""R6 follow-up 2026-05-28: asegurar que no hay `bare except` en producción.

`except:` (sin tipo) captura TODO, incluyendo `KeyboardInterrupt`,
`SystemExit` y `MemoryError` — eso oculta bugs catastróficos y rompe
Ctrl+C. PEP 8: "A bare `except:` clause will catch SystemExit and
KeyboardInterrupt exceptions, making it harder to interrupt a program
with Control-C, and can disguise other problems".

Estado actual (verificado 2026-05-28): 0 bare-except en `gemma4_agent/`
(el único bare en el repo está en `ui_field/node_modules/.../flatted.py`
que es vendored y no se ejecuta desde Python). Este test instala un hard
guard que falla si alguien introduce uno nuevo.
"""
from __future__ import annotations

import ast
import pathlib
import unittest


def _find_bare_except(path: pathlib.Path) -> list[int]:
    """Lista de linenos con `except:` (sin tipo) en `path`."""
    try:
        src = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.type is None
    ]


class TestNoBareExcept(unittest.TestCase):
    """Producción no debe usar `except:` (sin tipo).

    Usar `except Exception:` si es necesario tragar errores no fatales,
    o tipos específicos. Bare `except` rompe Ctrl+C y esconde bugs.
    """

    def test_no_bare_except_in_package(self):
        root = pathlib.Path(__file__).resolve().parent.parent  # gemma4_agent/
        offenders: list[str] = []
        for py in root.rglob("*.py"):
            if py.name == "test_no_bare_except.py":
                continue
            # Skip vendored deps (node_modules, etc).
            if "node_modules" in py.parts:
                continue
            for line_no in _find_bare_except(py):
                offenders.append(f"{py.relative_to(root.parent)}:{line_no}")
        self.assertEqual(
            offenders, [],
            "Bare `except:` encontrado(s). Reemplazar por "
            "`except Exception:` o un tipo específico:\n  "
            + "\n  ".join(offenders),
        )

    def test_no_bare_except_in_scripts(self):
        root = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts"
        offenders: list[str] = []
        for py in root.rglob("*.py"):
            for line_no in _find_bare_except(py):
                offenders.append(f"scripts/{py.relative_to(root)}:{line_no}")
        self.assertEqual(
            offenders, [],
            "Bare `except:` encontrado(s) en scripts/.\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
