"""Blind Claude judges for an e2e run whose oracle is a written criterion (the computer-use bank): no local judge, no
GPU. Each case of a bench_e2e run becomes an item with the person's turns, the case's "criterio", the steps BAXY ran
(operation, status, verified) and what BAXY said; the items are shuffled under random codes and split into batches of
at most --por cases, each one a prompt a Claude subagent judges in under 5 minutes without knowing the case ids.

    py scripts/renew/juez_ciego.py paquetes --casos <cases.json> --out <dir> [--por 6] <run>/results.jsonl ...
    (one subagent per <dir>/tanda_NN.md writes <dir>/veredictos_NN.json: {"<code>": {"cumple": bool, "motivo": str}})
    py scripts/renew/juez_ciego.py juntar --out <dir>

The key (code → case) stays in <dir>/clave.json, which no judge is given. juntar refuses a batch with no verdicts, a
verdict for a code the batch does not have, a code left unjudged and a verdict that is not a yes or no, so the result
(<dir>/resultado.json, summary first) is always every judged case once. A case whose turns never ran (void, setup
failed, session locked) is not judged and is listed apart; the oracle verdict of the run itself is not read."""
import argparse
import json
import random
import string
from pathlib import Path

INSTRUCCIONES = """Eres juez a ciegas de un asistente de voz para Windows (BAXY). Para cada caso tienes lo que pidió la
persona, el criterio escrito del caso, los pasos que BAXY ejecutó (operación, estado y si el resultado quedó
verificado) y lo que BAXY respondió. Decide sólo con eso: no supongas pasos que no están ni efectos que ningún paso
verificado muestra. Un caso cumple si se cumple su criterio entero; una respuesta que afirma como hecho algo que
ningún paso verificado respalda no cumple. Escribe en {veredictos} un JSON con una entrada por código:
{{"<código>": {{"cumple": true o false, "motivo": "una frase"}}}} y nada más."""


def _rows(run: Path) -> list[dict]:
    lines = [json.loads(line) for line in run.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in lines if "summary" not in row]


def paquetes(casos: Path, runs: list[Path], por: int, out: Path, semilla: int | None) -> list[Path]:
    if por < 1:
        raise SystemExit("--por must be at least 1")
    if out.exists() and any(out.iterdir()):  # verdicts of another run would be joined with this key
        raise SystemExit(f"{out} is not empty")
    bank = {str(case["id"]): case for case in json.loads(casos.read_text(encoding="utf-8"))}
    sin_criterio = sorted(i for i, case in bank.items() if not case.get("criterio"))
    if sin_criterio:
        raise SystemExit(f"{casos}: cases with no criterio {sin_criterio}")
    items, no_juzgados = [], []
    for run in runs:
        for row in _rows(run):
            if row["id"] not in bank:
                raise SystemExit(f"{run}: case {row['id']} is not in {casos}")
            if row.get("status") not in ("ok", "fallo"):  # void, setup_fallido, sesion_bloqueada: its turns never ran
                no_juzgados.append({"id": row["id"], "run": str(run), "status": row["status"]})
                continue
            case = bank[row["id"]]
            items.append({"id": row["id"], "run": str(run), "pedido": [
                {"dice": turn["text"], "si_pide_confirmacion": turn.get("reply_if_confirmation")}
                for turn in case["turns"]], "criterio": case["criterio"], "pasos": row.get("steps", []),
                "respuestas": [{"turno": r["turn"], "texto": r["text"]} for r in row.get("replies", [])]})
    ids = [(item["run"], item["id"]) for item in items]
    if len(set(ids)) != len(ids):
        raise SystemExit("a case appears twice in the same run")
    if not items:
        raise SystemExit("no case to judge")
    rng = random.Random(semilla)
    rng.shuffle(items)
    codes = set()
    while len(codes) < len(items):
        codes.add("".join(rng.choices(string.ascii_uppercase, k=3)))
    for item, code in zip(items, sorted(codes, key=lambda _: rng.random())):
        item["codigo"] = code
    out.mkdir(parents=True, exist_ok=True)
    clave, written = {}, []
    for number, start in enumerate(range(0, len(items), por), 1):
        tanda = items[start:start + por]
        veredictos = out / f"veredictos_{number:02d}.json"
        cuerpo = [{k: item[k] for k in ("codigo", "pedido", "criterio", "pasos", "respuestas")} for item in tanda]
        prompt = out / f"tanda_{number:02d}.md"
        prompt.write_text(INSTRUCCIONES.format(veredictos=veredictos) + "\n\n```json\n"
                          + json.dumps(cuerpo, ensure_ascii=False, indent=1) + "\n```\n", encoding="utf-8")
        written.append(prompt)
        for item in tanda:
            clave[item["codigo"]] = {"id": item["id"], "run": item["run"], "tanda": number}
    (out / "clave.json").write_text(json.dumps({"casos": str(casos), "clave": clave, "no_juzgados": no_juzgados},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    return written


def juntar(out: Path) -> dict:
    key = json.loads((out / "clave.json").read_text(encoding="utf-8"))
    clave = key["clave"]
    rows = []
    for number in sorted({entry["tanda"] for entry in clave.values()}):
        path = out / f"veredictos_{number:02d}.json"
        if not path.exists():
            raise SystemExit(f"{path} is missing: batch {number} was not judged")
        veredictos = json.loads(path.read_text(encoding="utf-8"))
        esperados = {code for code, entry in clave.items() if entry["tanda"] == number}
        if set(veredictos) != esperados:
            raise SystemExit(f"{path}: unjudged {sorted(esperados - set(veredictos))}, "
                             f"unknown {sorted(set(veredictos) - esperados)}")
        for code, verdict in veredictos.items():
            if not isinstance(verdict, dict) or not isinstance(verdict.get("cumple"), bool):
                raise SystemExit(f"{path}: {code} has no yes or no")
            rows.append({**clave[code], "codigo": code, "ok": verdict["cumple"], "motivo": verdict.get("motivo", "")})
    rows.sort(key=lambda row: (row["run"], row["id"]))
    summary = {"casos": key["casos"], "ok": sum(row["ok"] for row in rows), "n": len(rows),
               "no_juzgados": key["no_juzgados"]}
    (out / "resultado.json").write_text(json.dumps({"summary": summary, "casos": rows}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("paquetes")
    p.add_argument("--casos", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--por", type=int, default=6)
    p.add_argument("--semilla", type=int)
    p.add_argument("runs", type=Path, nargs="+")
    j = sub.add_parser("juntar")
    j.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "paquetes":
        for path in paquetes(args.casos, args.runs, args.por, args.out, args.semilla):
            print(path)
    else:
        print(json.dumps(juntar(args.out), ensure_ascii=False))


if __name__ == "__main__":
    main()
