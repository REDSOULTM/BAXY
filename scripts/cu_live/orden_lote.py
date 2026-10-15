"""Order of a live batch (lote.sh): cases of one app together, closed-app cases first, producers before consumers.

    python scripts/cu_live/orden_lote.py <case-id>...      prints the same ids, reordered, space separated

Rules (análisis r3a/estado_base.md, «Orden del lote»), all from data:
- cases of the same app (cases/v3_manifiesto.json "app"; "A + B" counts as A) run together, in the order each app
  first appears in the list, so a group ends with its app closed once (app_cerrada of the group);
- inside a group, a case whose states close the app (app_cerrada:*) runs before one that starts from it open;
- an app listed in estado/casos.json "orden.al_final" (elevated apps and apps behind a sign-in or update screen:
  their windows stay and cover the other cases) goes after the rest, and "orden.aparte" (the product's browser)
  last of all;
- a case that needs what another leaves (casos.json "requiere".tras) runs after it when both are in the batch;
- ids not in the manifest (s01, c3...) keep their place relative to each other, before the v3 groups.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LIVE = Path(__file__).resolve().parent


def _app(case: str, manifest: dict) -> str | None:
    entry = manifest.get(case.split("@", 1)[0])
    if not isinstance(entry, dict) or not entry.get("app"):
        return None
    return str(entry["app"]).split("+", 1)[0].strip()


def _closes_first(case: str, casos: dict) -> int:
    states = casos.get("casos", {}).get(case, [])
    return 0 if any(str(state).startswith("app_cerrada:") for state in states) else 1


def ordenar(ids: list[str], casos: dict, manifest: dict) -> list[str]:
    orden = casos.get("orden", {})
    al_final = set(orden.get("al_final", []))
    aparte = set(orden.get("aparte", []))
    sueltos = [case for case in ids if _app(case, manifest) is None]
    groups: dict[str, list[str]] = {}
    for case in ids:
        app = _app(case, manifest)
        if app is not None:
            groups.setdefault(app, []).append(case)
    tier = lambda app: 2 if app in aparte else 1 if app in al_final else 0  # noqa: E731
    apps = sorted(groups, key=lambda app: tier(app))  # stable: first appearance inside each tier
    out = list(sueltos)
    for app in apps:
        out += sorted(groups[app], key=lambda case: _closes_first(case, casos))
    # Producers before consumers: a dependent case moves right after the case it needs.
    for case, req in casos.get("requiere", {}).items():
        tras = req.get("tras") if isinstance(req, dict) else None
        if case in out and tras in out and out.index(case) < out.index(tras):
            out.remove(case)
            out.insert(out.index(tras) + 1, case)
    return out


def main(argv: list[str]) -> int:
    casos = json.loads((LIVE / "estado" / "casos.json").read_text(encoding="utf-8"))
    manifest = json.loads((LIVE / "cases" / "v3_manifiesto.json").read_text(encoding="utf-8"))
    print(" ".join(ordenar(argv, casos, manifest)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
