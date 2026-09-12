"""Comprueba los dos chequeos de estado de apertura contra los borradores reales de tres tandas.

`compose_visible_defect` es puro: se le pasan los borradores que APPS1029, REPAIR1030 y REPAIR1032
publicaron, con la `situation` exacta que recibió el compositor, y se ve qué rechaza ahora y qué sigue
limpio. Cubre las dos direcciones:

- `unstated_already_running`: el recibo dice que ya estaba en ejecución y la prosa se atribuye la
  apertura, o afirma un relanzamiento sobre el proceso reutilizado.
- `invented_prior_open_state`: el recibo dice que NO estaba en ejecución y la prosa da por anterior un
  estado que este turno acaba de crear.

Uso:
    python scratchpad/c03-open-state-check.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BASE = pathlib.Path.home() / "AppData/Local/BAXY"

# case_id por orden de respuesta publicada de app.open en cada tanda.
BATCHES = {
    "apps1029": ["H0085", "H0015", "H0055", "H0134", "H0136", "H0315", "H0317", "H0391",
                 "H0418", "H0544", "H0653", "apps1029-dev-01", "apps1029-dev-03",
                 "apps1029-dev-05"],
    "repair1030": ["H0015", "H0055", "H0134", "H0136", "H0391", "H0418", "H0653", "H0085",
                   "H0315", "H0317", "repair1030-dev-01", "repair1030-dev-02",
                   "repair1030-dev-03", "repair1030-dev-04"],
    "repair1032": ["H0251", "H0575", "H0588", "H0683", "H0706", "H0015", "H0055", "H0134",
                   "H0136", "H0391", "H0418", "H0653", "H0085", "H0315", "H0317",
                   "repair1032-dev-01", "repair1032-dev-02", "repair1032-dev-03",
                   "repair1032-dev-04", "repair1032-dev-05"],
}

RUNNING = "unstated_already_running"
PRIOR = "invented_prior_open_state"

EXPECTED = {
    # Se atribuían una apertura que el recibo niega (APPS1029).
    "Ya abrí Steam.": RUNNING,
    "Abrí Steam.": RUNNING,
    # Decía el hecho y añadía un relanzamiento inexistente (REPAIR1030 dev-02).
    "I opened Paint. The app was already running before, but I launched it again.": RUNNING,
    # Daba por anterior un estado que acababa de crear (REPAIR1032 H0575).
    "Ya tengo la calculadora abierta.": PRIOR,
    # Veraces: no se tocan.
    "Abrí Discord. La aplicación ya estaba en ejecución antes de abrirla.": "",
    "Sí, pude abrir Steam. Ya estaba en ejecución antes.": "",
    "I opened Steam. It was already running before.": "",
    "I opened Google Chrome. It was already running, so no new instance was started.": "",
    "Sure, Steam is already running.": "",
    "Abrí Paint.": "",
    "Ya abrí Paint.": "",
    "Ya está abierto Steam.": "",
    "Yeah, Steam is already open.": "",
    "La app ya estaba en ejecución antes de este turno.": "",
    "La app Steam ya estaba en ejecución antes de este turno.": "",
    "La app Steam ya estaba abierta.": "",
    "Paint was already open.": "",
    "Abrí la calculadora.": "",
    "Sure, I opened the calculator. It was not running before, and now it's active.": "",
    "I opened the calculator.": "",
    "Abrí la configuración de Windows.": "",
    "Abrí el Mapa de caracteres.": "",
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
            if position >= len(order):
                print(f"   ?? unmapped extra published reply: {draft[:60]}")
                failures += 1
                continue
            case_id = order[position]
            position += 1
            defect = compose_visible_defect(draft, "status", by_id[case_id]["text"],
                                            {"situation": situation})
            expected = EXPECTED.get(draft)
            total += 1
            if expected is None:
                print(f"   ?? unlisted draft: {draft[:70]}")
                failures += 1
                continue
            ok = defect == expected
            failures += 0 if ok else 1
            print(f"   {'OK ' if ok else 'BAD'} {case_id:18} want={expected or '(clean)':26} "
                  f"got={defect or '(clean)':26} {draft[:54]}")
    print(f"\n{total} drafts checked, {failures} mismatches")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
