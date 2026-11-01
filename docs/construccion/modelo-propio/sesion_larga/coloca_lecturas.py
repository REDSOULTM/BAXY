"""P0.6 (PC-R1-X3): pone en `lecturas` de un guion, en la ranura que lee el runner, el texto que cada turno debe recibir.

usage: py -3.12 -X utf8 coloca_lecturas.py SESION.json [...]

bench_sesion_larga.observation da a la llamada k (1..MAX_CALLS) del turno n el cuerpo que empieza en
lecturas[(n * MAX_CALLS + k) % len(lecturas)]: con los textos tal cual, un turno que lee «la nota de las reglas» recibe
el que toque por rotación, y el siguiente («mándale la hora que dice esa nota») no tiene el dato. Un turno con
`"lectura": i` recibe en sus llamadas el texto i de `lecturas_base` (los textos del guion; en la segunda y la tercera
también, para el browser.page.read que sigue a un browser.navigate); las demás ranuras llevan los textos por rotación.
Idempotente: se rehace siempre desde `lecturas_base`.
"""
import json
import sys
from pathlib import Path

MAX_CALLS = 3  # el de bench_sesion_larga


def coloca(session: dict) -> dict:
    base = session.get("lecturas_base") or session["lecturas"]
    last = max(t["n"] for t in session["turnos"])
    slots = [base[i % len(base)] for i in range(last * MAX_CALLS + MAX_CALLS + 1)]
    for turn in session["turnos"]:
        if "lectura" in turn:
            for call in range(1, MAX_CALLS + 1):
                slots[turn["n"] * MAX_CALLS + call] = base[turn["lectura"]]
    return {**session, "lecturas_base": base, "lecturas": slots}


for arg in sys.argv[1:]:
    path = Path(arg)
    session = coloca(json.loads(path.read_text(encoding="utf-8")))
    path.write_text(json.dumps(session, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{path.name}: {sum('lectura' in t for t in session['turnos'])} turnos con su texto, "
          f"{len(session['lecturas'])} ranuras")
