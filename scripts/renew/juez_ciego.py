"""Blind Claude judges for an e2e run whose oracle is a written criterion (the computer-use bank): no local judge, no
GPU. Each case of a bench_e2e run becomes an item with the person's turns, the case's "criterio", the steps BAXY ran
(operation, status, verified) and what BAXY said or asked; the items are shuffled under random codes and split into
batches of at most --por cases, each one a prompt a Claude subagent judges in under 5 minutes without knowing the case
ids. A case judged in several runs (base and candidate) never shares a batch with itself, so it is judged against its
criterion and not against its other run.

    py scripts/renew/juez_ciego.py paquetes --casos <cases.json> --out <dir> [--por 6] <run>/results.jsonl ...
    (one subagent per <dir>/tanda_NN.md writes <dir>/veredictos_NN.json: {"<code>": {"cumple": bool, "motivo": str}})
    py scripts/renew/juez_ciego.py juntar --out <dir>

The key (code → case) is written beside the folder, in <dir>.clave.json, out of the folder the judges write to.
juntar refuses a batch with no verdicts, a verdict for a code the batch does not have, a code left unjudged and a
verdict that is not a yes or no, so the result (<dir>/resultado.json) is always every judged case once. A case whose
turns never ran (setup failed, session locked, void) and a run that was void before any case are not judged and are
listed apart; the oracle verdict of the run itself is not read."""
import argparse
import json
import random
import string
from pathlib import Path

INSTRUCCIONES = """Eres juez a ciegas de un asistente de voz para Windows (BAXY). Para cada caso tienes lo que pidió la
persona, el criterio escrito del caso, los pasos que BAXY ejecutó (operación, estado y si el resultado quedó
verificado) y lo que BAXY respondió o preguntó en cada turno. Decide sólo con eso: no supongas pasos que no están ni
efectos que ningún paso verificado muestra. Un caso cumple si se cumple su criterio entero; una respuesta que afirma
como hecho algo que ningún paso verificado respalda no cumple. Juzga cada caso por separado. Escribe en {veredictos}
un JSON con una entrada por código:
{{"<código>": {{"cumple": true o false, "motivo": "una frase"}}}} y nada más."""


def _read(run: Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(line) for line in run.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines or "summary" not in lines[0]:
        raise SystemExit(f"{run}: no summary on its first line (not a bench_e2e run)")
    return lines[0]["summary"], lines[1:]


def _item(case: dict, row: dict, run: Path) -> dict:
    return {"id": row["id"], "run": str(run), "pedido": [
        {"dice": turn["text"], "si_pide_confirmacion": turn.get("reply_if_confirmation")} for turn in case["turns"]],
        "criterio": case["criterio"], "pasos": row.get("steps", []),
        "respuestas": [{"turno": r["turn"], "texto": r["text"], "pidio_confirmacion": r.get("asked_confirmation"),
                        "pregunta": r.get("confirmation_text"), "contestado": r.get("answered")}
                       for r in row.get("replies", [])]}


def _batches(items: list[dict], por: int) -> list[list[dict]]:
    batches: list[list[dict]] = []
    for item in items:
        room = [b for b in batches if len(b) < por and all(other["id"] != item["id"] for other in b)]
        if room:
            room[0].append(item)
        else:
            batches.append([item])
    return batches


def paquetes(casos: Path, runs: list[Path], por: int, out: Path, semilla: int | None) -> list[Path]:
    if por < 1:
        raise SystemExit("--por must be at least 1")
    clave_path = out.with_name(out.name + ".clave.json")
    if (out.exists() and any(out.iterdir())) or clave_path.exists():  # another run's verdicts would join this key
        raise SystemExit(f"{out} or {clave_path} already exists")
    bank = {str(case["id"]): case for case in json.loads(casos.read_text(encoding="utf-8"))}
    sin_criterio = sorted(i for i, case in bank.items() if not case.get("criterio"))
    if sin_criterio:
        raise SystemExit(f"{casos}: cases with no criterio {sin_criterio}")
    items, no_juzgados = [], []
    for run in runs:
        summary, rows = _read(run)
        if summary.get("void") and not rows:
            no_juzgados.append({"run": str(run), "status": "void", "motivo": summary["void"]})
            continue
        if len(rows) != summary.get("n"):
            raise SystemExit(f"{run}: {len(rows)} rows but its summary says n={summary.get('n')}")
        for row in rows:
            if row["id"] not in bank:
                raise SystemExit(f"{run}: case {row['id']} is not in {casos}")
            if row.get("status") not in ("ok", "fallo"):  # void, setup_fallido, sesion_bloqueada: its turns never ran
                no_juzgados.append({"id": row["id"], "run": str(run), "status": row.get("status")})
            else:
                items.append(_item(bank[row["id"]], row, run))
    ids = [(item["run"], item["id"]) for item in items]
    if len(set(ids)) != len(ids):
        raise SystemExit("a case appears twice in the same run")
    if not items:
        raise SystemExit("no case to judge")
    rng = random.Random(semilla)
    rng.shuffle(items)
    codes: set[str] = set()
    while len(codes) < len(items):
        codes.add("".join(rng.choices(string.ascii_uppercase, k=3)))
    for item, code in zip(items, rng.sample(sorted(codes), len(codes))):
        item["codigo"] = code
    out.mkdir(parents=True, exist_ok=True)
    clave, written = {}, []
    for number, tanda in enumerate(_batches(items, por), 1):
        cuerpo = [{k: item[k] for k in ("codigo", "pedido", "criterio", "pasos", "respuestas")} for item in tanda]
        prompt = out / f"tanda_{number:02d}.md"
        prompt.write_text(INSTRUCCIONES.format(veredictos=out / f"veredictos_{number:02d}.json") + "\n\n```json\n"
                          + json.dumps(cuerpo, ensure_ascii=False, indent=1) + "\n```\n", encoding="utf-8")
        written.append(prompt)
        for item in tanda:
            clave[item["codigo"]] = {"id": item["id"], "run": item["run"], "tanda": number}
    clave_path.write_text(json.dumps({"casos": str(casos), "clave": clave, "no_juzgados": no_juzgados},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    return written


def juntar(out: Path) -> dict:
    key = json.loads(out.with_name(out.name + ".clave.json").read_text(encoding="utf-8"))
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
    por_run = {}
    for row in rows:
        ok, n = por_run.get(row["run"], (0, 0))
        por_run[row["run"]] = (ok + row["ok"], n + 1)
    summary = {"casos": key["casos"], "ok": sum(row["ok"] for row in rows), "n": len(rows),
               "por_corrida": {run: {"ok": ok, "n": n} for run, (ok, n) in por_run.items()},
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
