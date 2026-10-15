"""Agregado de molestia por lote.

Uso:
  py -3.12 molestia_sum.py <salida de batch.sh | molestia.json | carpeta de evidencia | id de caso>...
  py -3.12 molestia_sum.py --linea <molestia.json>      # sólo la línea de resumen de un caso
Los ids se buscan en %LOCALAPPDATA%\\BAXY\\cu-universal-evidencia\\v2-<id>\\molestia.json (o CU_EVIDENCE).
Los casos con el dueño activo se listan pero quedan fuera del total: su input real impide atribuir.
"""
import json
import os
import re
import sys

KEYS = ("perdidos", "insertados", "teclas_baxy_en_ventana_usuario", "teclas_uia", "robos_foco", "ms_robados",
        "movimientos_cursor", "cursor_vueltas_restauradas", "clics", "actos_fuera_de_pausa", "rafagas",
        "rafagas_restauradas", "rafagas_restauradas_tarde", "primer_plano_transitorios")
SHORT = ("perd", "ins", "teclas", "uia", "robos", "ms_rob", "cursor", "vueltas", "clics", "fuera_p", "raf", "rest",
         "tarde", "transit")


def evidence_base():
    if os.environ.get("CU_EVIDENCE"):
        return os.environ["CU_EVIDENCE"]
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "BAXY", "cu-universal-evidencia")


def resolve(arg):
    """-> [(caso, ruta de molestia.json)]"""
    if arg.endswith(".json"):
        return [(os.path.basename(os.path.dirname(os.path.abspath(arg))), arg)]
    if os.path.isdir(arg):
        return [(os.path.basename(os.path.abspath(arg)), os.path.join(arg, "molestia.json"))]
    if os.path.isfile(arg):
        text = open(arg, encoding="utf-8", errors="replace").read()
        ids = re.findall(r"^=+ (\S+)", text, re.M)
        return [(i, os.path.join(evidence_base(), "v2-" + i, "molestia.json")) for i in ids]
    return [(arg, os.path.join(evidence_base(), "v2-" + arg, "molestia.json"))]


def main(argv):
    if len(argv) >= 2 and argv[0] == "--linea":
        try:
            with open(argv[1], encoding="utf-8") as f:
                print(json.load(f)["resumen"])
        except (OSError, ValueError, KeyError):
            print("molestia: sin medición (no hay molestia.json; ¿CU_MOLESTIA=0?)")
        return 0
    cases = [c for a in argv for c in resolve(a)]
    if not cases:
        print(__doc__)
        return 2
    total = dict.fromkeys(KEYS, 0)
    counted = excluded = missing = not_front = not_cursor = 0
    print("caso | " + " | ".join(SHORT) + " | final | dueño")
    for name, path in cases:
        try:
            with open(path, encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, ValueError):
            missing += 1
            print(f"{name} | sin molestia.json")
            continue
        if not r.get("medido"):
            missing += 1
            print(f"{name} | {r.get('resumen')}")
            continue
        fin = r.get("final", {})
        front, cur = fin.get("frente_usuario"), fin.get("cursor_en_su_posicion")
        row = " | ".join(str(r.get(k, 0)) for k in KEYS)
        print(f"{name} | {row} | {'F' if front else 'f'}{'C' if cur else 'c'} | "
              f"{'ACTIVO (excluido)' if r.get('dueno_activo') else '-'}")
        if r.get("dueno_activo"):
            excluded += 1
            continue
        counted += 1
        for k in KEYS:
            total[k] += r.get(k, 0) or 0
        not_front += 0 if front else 1
        not_cursor += 0 if cur else 1
    pct = f"{100.0 * total['rafagas_restauradas'] / total['rafagas']:.1f} %" if total["rafagas"] else "—"
    print(f"\nLOTE: casos={counted} (dueño activo excluidos={excluded}, sin medición={missing}) "
          f"perdidos={total['perdidos']} insertados={total['insertados']} "
          f"teclas_baxy_en_ventana_usuario={total['teclas_baxy_en_ventana_usuario']} robos={total['robos_foco']} "
          f"ms_robados={total['ms_robados']} movimientos_cursor={total['movimientos_cursor']} clics={total['clics']} "
          f"actos_fuera_de_pausa={total['actos_fuera_de_pausa']} restauradas={total['rafagas_restauradas']}/"
          f"{total['rafagas']} ({pct}) restauradas_tarde={total['rafagas_restauradas_tarde']} "
          f"teclas_uia={total['teclas_uia']} vueltas_cursor={total['cursor_vueltas_restauradas']} "
          f"primer_plano_transitorios={total['primer_plano_transitorios']} "
          f"final_sin_frente={not_front} final_sin_cursor={not_cursor}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
