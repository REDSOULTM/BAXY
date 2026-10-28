"""P0.6 (PC-R1-X3): comprueba, sin GPU, que el runner del banco de sesión larga lee un guion como lee sesion50-s0.json.

usage: py -3.12 -X utf8 valida_guiones.py <worktree con scripts/renew/bench_sesion_larga.py> SESION.json [...]

Por guion: forma (version, turnos con n sin huecos, id = L{n:02d}-{bank}-{case}, lecturas largas); cada operación y
argumento del expect existen en el catálogo de ses.sh y los códigos de lista cerrada son de su lista; la categoría es la
que bench_sesion_larga.category deduce; bench_decision.judge da por bueno cada expect ante su decisión ideal y por malo
ante una contestación «listo»; las tandas de 10 que corre ses.sh salen como en correr (turnos desde..hasta), y
observation da a cada lectura y búsqueda un cuerpo de las lecturas del guion.
"""
import json
import re
import sys
from pathlib import Path

WT = Path(sys.argv[1])
sys.path.insert(0, str(WT / "scripts" / "renew"))
import bench_decision  # noqa: E402
import bench_sesion_larga as bsl  # noqa: E402

CATALOG = json.loads(Path(r"F:\BAXYeval\renew_v6\catalog-final8c.json").read_text(encoding="utf-8"))
CAPS = {c["name"]: c for c in CATALOG["capabilities"]}
RISK = {name: str(c.get("risk") or "") for name, c in CAPS.items()}
ENUMS = bench_decision.enums_of(CATALOG)


def ideal(expect: dict) -> tuple[dict, dict | None]:
    """La decisión que cumple el expect (la primera opción de un any), y sus argumentos."""
    kind = expect["kind"]
    if kind == "any":
        return ideal(expect["options"][0])
    if kind == "call":
        return {"kind": "action", "operation": expect["op"]}, dict(expect.get("args") or {})
    if kind == "call_any":
        return {"kind": "action", "operation": expect["ops"][0]}, {}
    if kind == "ask":
        return {"kind": "clarify", "question": "¿Cuál?"}, None
    return {"kind": "conversation", "reply": "Te cuento: eso no lo puedo hacer desde el PC."}, None


def sin_re(expect: dict) -> dict:
    """El expect sin los argumentos «re:» (la decisión ideal no sabe escribir un valor que cumpla una regex; ésas se
    comprueban sólo como regex válidas)."""
    if expect["kind"] == "any":
        return {**expect, "options": [sin_re(o) for o in expect["options"]]}
    if expect["kind"] == "call":
        return {**expect, "args": {k: v for k, v in (expect.get("args") or {}).items() if not str(v).startswith("re:")}}
    return expect


def ops_of(expect: dict) -> list[tuple[str, dict]]:
    if expect["kind"] == "any":
        return [p for o in expect["options"] for p in ops_of(o)]
    if expect["kind"] == "call":
        return [(expect["op"], expect.get("args") or {})]
    if expect["kind"] == "call_any":
        return [(op, {}) for op in expect["ops"]]
    return []


def valida(path: Path) -> list[str]:
    errs: list[str] = []
    s = json.loads(path.read_text(encoding="utf-8"))
    turns, lecturas = s.get("turnos") or [], s.get("lecturas") or []
    if s.get("version") != 1:
        errs.append("version != 1")
    if [t["n"] for t in turns] != list(range(1, len(turns) + 1)):
        errs.append("n con huecos o desordenado")
    if not 40 <= len(turns) <= 60:
        errs.append(f"{len(turns)} turnos (se piden 40-60)")
    if len(lecturas) < 5 or min(map(len, lecturas)) < 1000:
        errs.append(f"lecturas: {len(lecturas)}, la más corta {min(map(len, lecturas), default=0)} caracteres")
    for t in turns:
        where = f"turno {t.get('n')}"
        if t.get("id") != f"L{t['n']:02d}-{t.get('bank')}-{t.get('case')}":
            errs.append(f"{where}: id {t.get('id')}")
        if not str(t.get("text") or "").strip():
            errs.append(f"{where}: sin texto")
        e = t["expect"]
        for op, args in ops_of(e):
            if op not in CAPS:
                errs.append(f"{where}: {op} no está en el catálogo")
                continue
            if bench_decision.current(op)[0] is None:
                errs.append(f"{where}: {op} está retirada en catalog_equivalence (el juez no cuenta el turno)")
            props = (CAPS[op].get("argumentsSchema") or {}).get("properties") or {}
            for k, v in args.items():
                if k not in props:
                    errs.append(f"{where}: {op} no tiene el argumento {k}")
                elif (codes := (ENUMS.get(op) or {}).get(k)) and not str(v).startswith("re:") \
                        and bench_decision.norm(v).strip() not in codes:
                    errs.append(f"{where}: {op}.{k}={v} no es de su lista")
                elif isinstance(v, str) and v.startswith("re:"):
                    re.compile(v[3:])
        for key in ("reply_re", "reply_not_re"):
            for spec in ([e[key]] if isinstance(e.get(key), str) else e.get(key) or []):
                re.compile(spec)
        if (cat := bsl.category(e, RISK)) != t.get("category"):
            errs.append(f"{where}: category {t.get('category')}, el runner deduce {cat}")
        decision, arguments = ideal(e)
        ok = bench_decision.judge(sin_re(e), decision, arguments, ENUMS)
        if ok is not True and not (e["kind"] == "text" and e.get("reply_re")):  # la contestación ideal no la sabe
            errs.append(f"{where}: el juez no acepta la decisión ideal ({ok})")
        if bench_decision.judge(e, {"kind": "conversation", "reply": "listo, hecho"}, None, ENUMS) is True \
                and "text" not in {o["kind"] for o in e.get("options") or [e]}:
            errs.append(f"{where}: el juez acepta «listo, hecho» en un turno {e['kind']}")
        if "lectura" in t:  # el texto que el turno debe recibir, en la ranura que lee su primera llamada
            got = json.loads(bsl.observation("file.read", {}, "read_only", lecturas, t["n"] * bsl.MAX_CALLS + 1))
            if not got["observed"]["text"].startswith(s["lecturas_base"][t["lectura"]][:500]):
                errs.append(f"{where}: no recibe su lectura {t['lectura']} (falta coloca_lecturas.py)")
    # Las tandas de ses.sh (10 turnos) como las corta correr, y el cuerpo que observation da a lecturas y búsquedas.
    for desde in range(1, len(turns) + 1, 10):
        tanda = [t for t in turns if desde <= t["n"] <= desde + 9]
        if not tanda:
            errs.append(f"tanda {desde}: vacía")
        for t in tanda:
            for op, args in ops_of(t["expect"])[:1]:
                body = json.loads(bsl.observation(op, args, RISK.get(op, ""), lecturas, t["n"] * bsl.MAX_CALLS + 1))
                if (op == "web.search" or RISK.get(op) in bsl.READ_RISKS) and not body["observed"]:
                    errs.append(f"turno {t['n']}: observation sin cuerpo para {op}")
    return errs


def main() -> None:
    bad = 0
    for arg in sys.argv[2:]:
        path = Path(arg)
        s = json.loads(path.read_text(encoding="utf-8"))
        cats: dict[str, int] = {}
        fams: dict[str, int] = {}
        for t in s["turnos"]:
            cats[t["category"]] = cats.get(t["category"], 0) + 1
            fams[str(t.get("family"))] = fams.get(str(t.get("family")), 0) + 1
        errs = valida(path)
        bad += bool(errs)
        print(f"{path.name}: {len(s['turnos'])} turnos, {len(s.get('lecturas') or [])} lecturas, "
              f"tandas {-(-len(s['turnos']) // 10)}; {cats}; {fams}; {'OK' if not errs else f'{len(errs)} errores'}")
        for e in errs:
            print("   ", e)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
