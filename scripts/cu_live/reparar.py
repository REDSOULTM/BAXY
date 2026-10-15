"""Whether batch.sh repeats the base states of a case once more («se repara una vez»), harness only.

Pasada r9 + r11 (2026-10-08, 105 cases): the repair ran in 85 cases and fixed NOTHING (0 of 129 failing states). It
cost 8.7 s of median a case (sin_restos + estado_base again; 15 s with a OneNote leftover that never closes). The
failures it repeated were permanent: a leftover the harness refuses to close (ventanas_nuevas: a window nobody
recorded, maybe the person's), the person's window of the case's app (ajena_abierta, pestanas_ajenas), a state that
threw (error), the elevated always-on-top keyboard (sin_obstaculos), or a OneNote whose close failed every time.

  py -3.12 reparar.py decidir --registro <file>   stdin: the state lines of the first pass
      prints «reparar» or «permanente <key> ...»: every failing state is permanent by its kind, or the same failure
      already survived a repair in this batch (registry, 10 min: then it is tried again).
  py -3.12 reparar.py anotar --registro <file>    stdin: the lines of the first pass, «@@reparado@@», those of the second
      a failure the repair left exactly as it was goes to the registry.
The case's lines and its AVISO are the same either way: a state that does not verify still stops the case
(CU_ESTADO_ESTRICTO=1) or runs it flagged (=0); only the repetition that changed nothing is not done.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

VIGENCIA_S = 600.0
# Results a repeat cannot change: the person's window (never touched), a state that threw.
RESULTADOS_PERMANENTES = {"error", "ajena_abierta", "pestanas_ajenas", "bloc_ajeno_abierto"}


def fallos(lineas: list[str]) -> list[dict]:
    out = []
    for ln in lineas:
        ln = ln.strip()
        if not ln.startswith('{"estado"'):
            continue
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        if j.get("verificado") is False:
            out.append(j)
    return out


def clave(j: dict) -> str:
    k = f'{j.get("estado")}|{j.get("resultado")}'
    if j.get("quedan"):
        k += "|" + ",".join(sorted(str(q) for q in j["quedan"]))
    return k


def permanente_por_tipo(j: dict) -> bool:
    estado = str(j.get("estado", ""))
    if estado == "sin_obstaculos":
        return True  # an elevated always-on-top window: the harness cannot close it
    if j.get("resultado") in RESULTADOS_PERMANENTES:
        return True
    if estado == "sin_restos" and j.get("resultado") == "no_verificado":
        # «nombre:pid:motivo»: every motivo a refusal (ventanas_nuevas, ventana_de_otro_proceso, an Office document that
        # is not the harness's...). ventana_viva is a close that was tried and failed: only the registry says it stays.
        quedan = [str(q) for q in j.get("quedan") or []]
        return bool(quedan) and all(q.split(":", 2)[-1] != "ventana_viva" for q in quedan)
    return False


def leer_registro(ruta: str, ahora: float) -> dict:
    try:
        with open(ruta, encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: t for k, t in r.items() if isinstance(t, (int, float)) and ahora - t < VIGENCIA_S}


def decidir(lineas: list[str], registro: dict) -> tuple[bool, list[str]]:
    """(reparar, keys): repair unless every failure is permanent by kind or already in the registry."""
    f = fallos(lineas)
    keys = [clave(j) for j in f]
    reparar = any(not permanente_por_tipo(j) and clave(j) not in registro for j in f)
    return reparar, keys


def anotar(lineas: list[str], registro: dict, ahora: float) -> dict:
    limpias = [ln.strip() for ln in lineas]
    if "@@reparado@@" not in limpias:
        return registro
    i = limpias.index("@@reparado@@")
    antes = {clave(j) for j in fallos(lineas[:i])}
    for j in fallos(lineas[i + 1:]):
        if clave(j) in antes:
            registro[clave(j)] = ahora
    return registro


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=("decidir", "anotar"))
    ap.add_argument("--registro", required=True)
    a = ap.parse_args(argv)
    lineas = sys.stdin.read().splitlines()
    ahora = time.time()
    registro = leer_registro(a.registro, ahora)
    if a.accion == "decidir":
        reparar, keys = decidir(lineas, registro)
        print("reparar" if reparar else "permanente " + " ".join(k.replace(" ", "_") for k in keys))
        return 0
    registro = anotar(lineas, registro, ahora)
    tmp = a.registro + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(registro, f)
    os.replace(tmp, a.registro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
