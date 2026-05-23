"""Validador standalone de stubs vs schemas.

NO importa Carter. Solo verifica que cada tool en tool_schemas.json tiene
una stub impl en stubs.py. tool_schemas.json fue generado una sola vez
y queda fijo (snapshot del catalogo).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "tool_schemas.json"


def main() -> int:
    if not SCHEMAS.exists():
        print(f"[validate] FALTA {SCHEMAS}")
        return 1

    schemas = json.loads(SCHEMAS.read_text(encoding="utf-8"))
    schema_names = {s["function"]["name"] for s in schemas}
    print(f"[validate] schemas: {len(schema_names)} tools")

    sys.path.insert(0, str(ROOT))
    import stubs  # noqa: E402

    impl_names = set(stubs._STUBS.keys())
    print(f"[validate] stub impls: {len(impl_names)} tools")

    missing_impl = schema_names - impl_names
    extra_impl = impl_names - schema_names
    if missing_impl:
        print(f"[validate] FALTAN impls para: {sorted(missing_impl)}")
        return 1
    if extra_impl:
        print(f"[validate] WARN impls extra (no en schemas): {sorted(extra_impl)}")

    # Smoke: invocar cada stub con args vacios
    print("[validate] smoke testing all stubs...")
    failures = []
    for name in schema_names:
        try:
            r = stubs.execute_tool(name, {})
            if not isinstance(r, dict):
                failures.append((name, f"return not dict: {type(r)}"))
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {exc}"))
    if failures:
        print(f"[validate] {len(failures)} stub failures:")
        for n, e in failures[:10]:
            print(f"  {n}: {e}")
        return 1
    print(f"[validate] all {len(schema_names)} stubs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
