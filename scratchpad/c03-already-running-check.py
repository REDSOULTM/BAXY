"""Comprueba el chequeo de «ya estaba en ejecución» contra los borradores reales de las dos tandas.

Sobre APPS1029 —antes de la reparación— y sobre REPAIR1030 —después—, con la `situation` exacta que
recibió el compositor en cada vuelta. Añade lo que REPAIR1030 enseñó: decir el hecho y a la vez
afirmar un relanzamiento no vale, y la frase fija que salió de la instrucción anterior no debe volver.

Uso:
    python scratchpad/c03-already-running-check.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BASE = pathlib.Path.home() / "AppData/Local/BAXY"

# case_id por orden de respuesta publicada de app.open en cada tanda, y qué espera raíz de cada
# borrador: limpio, o rechazado con `unstated_already_running`.
BATCHES = {
    "apps1029": ["H0085", "H0015", "H0055", "H0134", "H0136", "H0315", "H0317", "H0391",
                 "H0418", "H0544", "H0653", "apps1029-dev-01", "apps1029-dev-03",
                 "apps1029-dev-05"],
    "repair1030": ["H0015", "H0055", "H0134", "H0136", "H0391", "H0418", "H0653", "H0085",
                   "H0315", "H0317", "repair1030-dev-01", "repair1030-dev-02",
                   "repair1030-dev-03", "repair1030-dev-04"],
}

REJECT = "unstated_already_running"
EXPECTED = {
    # APPS1029: los ocho que se atribuían el lanzamiento.
    "Ya abrí Steam.": REJECT,
    "Abrí Steam.": REJECT,
    # APPS1029: los fieles, que no deben moverse.
    "Abrí Discord. La aplicación ya estaba en ejecución antes de abrirla.": "",
    "Sí, pude abrir Steam. Ya estaba en ejecución antes.": "",
    "I opened Steam. It was already running before.": "",
    "I opened Google Chrome. It was already running, so no new instance was started.": "",
    "Sure, Steam is already running.": "",
    "Abrí Paint.": "",
    # REPAIR1030: la frase fija que copió la instrucción anterior sigue siendo veraz, así que
    # este chequeo no la rechaza; lo que la descarta es el invariante de frase fija, en la
    # adjudicación. Se lista para que su clasificación quede explícita y no por olvido.
    "La app ya estaba en ejecución antes de este turno.": "",
    "La app Steam ya estaba en ejecución antes de este turno.": "",
    "Ya abrí Paint.": "",
    "I opened Paint. The app was already running before, but I launched it again.": REJECT,
    "Ya está abierto Steam.": "",
    "Yeah, Steam is already open.": "",
}


def main() -> int:
    from baxy_mind.llm import compose_visible_defect

    failures = 0
    total = 0
    for batch, order in BATCHES.items():
        run = BASE / f"C03-{batch}-private/run"
        panel = json.loads((BASE / f"C03-{batch}-proposal/panel.json").read_text(encoding="utf-8"))
        by_id = {case["case_id"]: case for case in panel}
        rows = [json.loads(line) for line in
                (run / "compose-audit.jsonl").read_text(encoding="utf-8-sig").splitlines()
                if line.strip()]
        print(f"== {batch}")
        position = 0
        for row in rows:
            if row.get("intent") != "status" or not row.get("published"):
                continue
            situation = row.get("situation")
            draft = (row.get("draft") or "").strip()
            if not draft or not isinstance(situation, str):
                continue
            if json.loads(situation).get("operation") != "app.open":
                continue
            case_id = order[position]
            position += 1
            user_text = by_id[case_id]["text"]
            defect = compose_visible_defect(draft, "status", user_text, {"situation": situation})
            expected = EXPECTED.get(draft)
            total += 1
            if expected is None:
                print(f"   ?? unlisted draft: {draft[:80]}")
                failures += 1
                continue
            ok = defect == expected
            failures += 0 if ok else 1
            print(f"   {'OK ' if ok else 'BAD'} {case_id:18} want={expected or '(clean)':26} "
                  f"got={defect or '(clean)':26} {draft[:58]}")
    print(f"\n{total} drafts checked, {failures} mismatches")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
