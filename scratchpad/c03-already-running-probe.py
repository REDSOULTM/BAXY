"""Comprueba la reparación del hecho «ya estaba en ejecución» contra la tanda real, sin GPU.

`compose_visible_defect` es una función pura: se le pueden pasar los borradores exactos que APPS1029
publicó, con la `situation` exacta que recibió el compositor, y ver si el defecto se detecta ahora y
si algo que hoy cumple deja de cumplir. Eso es lo que decide si la reparación se mide en el producto,
no una opinión sobre el prompt.

Uso:
    python scratchpad/c03-already-running-probe.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUN = pathlib.Path.home() / "AppData/Local/BAXY/C03-apps1029-private/run"
PANEL = pathlib.Path.home() / "AppData/Local/BAXY/C03-apps1029-proposal/panel.json"

# Veredicto de raíz en APPS1029: qué debe seguir limpio y qué debe quedar rechazado ahora.
EXPECTED_CLEAN = {
    "Sí, pude abrir Steam. Ya estaba en ejecución antes.",
    "I opened Steam. It was already running before.",
    "Sure, Steam is already running.",
    "Abrí Discord. La aplicación ya estaba en ejecución antes de abrirla.",
    "I opened Google Chrome. It was already running, so no new instance was started.",
    "Abrí Paint.",  # lanzamiento real: alreadyRunning=false, no debe tocarse
}
EXPECTED_REJECTED = {
    "Ya abrí Steam.",
    "Abrí Steam.",
}


def main() -> int:
    from baxy_mind.llm import compose_visible_defect

    rows = [json.loads(line) for line in
            (RUN / "compose-audit.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    by_text = {case["text"]: case for case in panel}

    # Las catorce respuestas publicadas de app.open, en el orden de la tanda.
    # Se nombran para que cada borrador se valide con SU literal: pasarle otro
    # cambia el idioma esperado y el defecto que sale es el de idioma, no éste.
    ORDER = ["H0085", "H0015", "H0055", "H0134", "H0136", "H0315", "H0317", "H0391",
             "H0418", "H0544", "H0653", "apps1029-dev-01", "apps1029-dev-03",
             "apps1029-dev-05"]
    by_id = {case["case_id"]: case for case in panel}

    checked: list[tuple[str, str, str, str]] = []
    position = 0
    for row in rows:
        if row.get("intent") != "status" or not row.get("published"):
            continue
        situation = row.get("situation")
        draft = (row.get("draft") or "").strip()
        if not draft or not isinstance(situation, str):
            continue
        parsed = json.loads(situation)
        if parsed.get("operation") != "app.open":
            continue
        case_id = ORDER[position] if position < len(ORDER) else "?"
        position += 1
        user_text = by_id[case_id]["text"] if case_id in by_id else ""
        defect = compose_visible_defect(draft, "status", user_text,
                                        {"situation": situation})
        checked.append((case_id, draft, defect, user_text))

    failures = []
    for name, draft, defect, user_text in checked:
        expectation = ("clean" if draft in EXPECTED_CLEAN
                       else "rejected" if draft in EXPECTED_REJECTED else "unlisted")
        ok = ((expectation == "clean" and defect == "")
              or (expectation == "rejected" and defect == "unstated_already_running"))
        if not ok:
            failures.append((name, draft, defect, expectation))
        print(f"{'OK ' if ok else 'BAD'} {expectation:9} defect={defect or '(none)':28} "
              f"{draft[:70]}")
    print(f"\nchecked {len(checked)} published app.open replies; mismatches {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
