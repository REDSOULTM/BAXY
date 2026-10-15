"""¿Hay que repetir el caso? Lee el events.jsonl de una corrida del conductor (cu_live.sh) y dice si no pudo correr
por la infraestructura, no por BAXY. batch.sh lo repite entonces, igual que con otro BAXY abierto o la GPU ocupada.

Motivos:
  runtime_not_ready     el Core no quedó listo (terminal blocked_environment).
  decision_unavailable  el decisor no respondió (decisor recalentándose, GPU tomada por otros procesos) y el turno
                        terminó sin final (terminal sin final con diagnóstico no_response): medido en s02 r2, 171 s.
Un turno sin final SIN decision_unavailable es un silencio del producto y cuenta contra BAXY: no se repite. Tampoco un
decision_unavailable cuyo turno sí publicó un final (el respaldo de conversación respondió).

Uso: py -3.12 repetir.py <events.jsonl>   imprime el motivo y sale 0 si hay que repetir; 1 si no.
"""
import json
import sys


def _turnos(lines):
    """Agrupa las líneas por turno: cada `admission` del conductor (command=turn) abre un turno, y su terminal y sus
    posteriores son de ese turno. Sin admisiones (o con dos terminales seguidos) cada terminal abre el suyo."""
    turnos, cur = [], None
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        kind = d.get("type")
        if kind == "admission" and d.get("command") == "turn":
            cur = {"terminal": None, "posteriores": []}
            turnos.append(cur)
        elif kind == "terminal":
            if cur is None or cur["terminal"] is not None:
                cur = {"terminal": None, "posteriores": []}
                turnos.append(cur)
            cur["terminal"] = d
        elif kind == "posterior" and cur is not None:
            cur["posteriores"].append(d)
    return turnos


def motivo_repeticion(lines):
    turnos = _turnos(lines)
    for t in turnos:
        term = t["terminal"] or {}
        if term.get("kind") == "blocked_environment" and term.get("diagnostic") == "runtime_not_ready":
            return "runtime_not_ready"
    # El decisor no disponible cuenta sólo en el MISMO turno que terminó sin final: un turno que publicó su final
    # por el respaldo y otro que calló con el decisor respondiendo son dos cosas distintas (el silencio cuenta).
    for t in turnos:
        term = t["terminal"]
        if term is None or term.get("final") or "no_response" not in str(term.get("diagnostic") or ""):
            continue
        if "decision_unavailable" in str(term.get("diagnostic") or "") or any(
                p.get("mindReplyRejection") == "decision_unavailable" for p in t["posteriores"]):
            return "decision_unavailable"
    return None


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    try:
        with open(argv[0], encoding="utf-8-sig", errors="replace") as f:
            motivo = motivo_repeticion(f)
    except OSError:
        return 1
    if motivo:
        print(motivo)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
