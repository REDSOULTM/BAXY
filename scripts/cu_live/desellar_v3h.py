"""Desella el lote de generalización v3h (escrito por un subagente que no vio el repositorio) justo antes de su
única corrida: comprueba el sha256 sellado, escribe cases/v3h-*.turns y añade sus filas al manifiesto. No imprime
el contenido de las órdenes, sólo los ids, para que nadie lo lea antes de correrlo.

uso: py -3.12 scripts/cu_live/desellar_v3h.py <sellado/v3h.json> <sha256 esperado>
"""
import hashlib
import json
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "cases"


def main() -> int:
    source, expected = Path(sys.argv[1]), sys.argv[2].lower()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != expected:
        print(f"sha256 distinto: {digest} != {expected}", file=sys.stderr)
        return 2
    cases = json.loads(source.read_text(encoding="utf-8"))["cases"]
    manifest_path = CASES / "v3_manifiesto.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = []
    for case in cases:
        case_id = case["id"]
        if not case_id.startswith("v3h-"):
            raise ValueError(f"id inesperado: {case_id}")
        (CASES / f"{case_id}.turns").write_text(
            "\n".join(turn.strip() for turn in case["turns"]) + "\n", encoding="utf-8", newline="\n")
        manifest[case_id] = {key: case.get(key, "") for key in ("app", "lang", "turns", "verify", "setup", "safety")}
        ids.append(case_id)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (CASES / "V3H.txt").write_text(" ".join(ids) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(ids)} casos desellados: {' '.join(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
