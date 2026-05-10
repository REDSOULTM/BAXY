"""Analisis historico exhaustivo: agrupa fails de TODAS las versiones por
caso ID y por causa raiz. Identifica patrones persistentes vs flaky.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"

VERSIONS = ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12"]


def load_version(v):
    p = RESULTS / f"full540_{v}_Q6_K_FULL.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    versions = {v: load_version(v) for v in VERSIONS}

    # Por cada caso, traquear: en qué versiones falló
    fails_per_case = defaultdict(list)  # cid -> [(version, status, reasons, reply, tools)]
    pass_per_case = defaultdict(list)
    for v, d in versions.items():
        if not d:
            continue
        for r in d["results"]:
            cid = r["cid"]
            if r.get("status") == "PASS":
                pass_per_case[cid].append(v)
            else:
                fails_per_case[cid].append({
                    "version": v,
                    "status": r["status"],
                    "reasons": r.get("reasons", []),
                    "reply": (r.get("reply") or "")[:200],
                    "tools": r.get("tools", []),
                    "latency": r.get("latency_ms", 0),
                })

    # Persistente = falló en >50% de las versiones (fails reales del modelo o spec)
    # Flaky = falló en 1-2 versiones (probablemente regresión por cambios)
    # Resuelto = falló en versiones tempranas pero v10+ pasa
    n = sum(1 for d in versions.values() if d)
    persistent = []
    flaky = []
    resolved = []
    for cid, fails in fails_per_case.items():
        v_set = {f["version"] for f in fails}
        # Resuelto si las últimas 3 versiones pasan
        last_3 = ["v10", "v11", "v12"]
        passed_last3 = all(v in pass_per_case[cid] for v in last_3 if versions.get(v))
        if passed_last3:
            resolved.append((cid, fails))
        elif len(v_set) > n / 2:
            persistent.append((cid, fails))
        else:
            flaky.append((cid, fails))

    print(f"Versiones analizadas: {n}")
    print(f"Casos con al menos 1 fail: {len(fails_per_case)}")
    print(f"  Resueltos (pasan en v10/v11/v12): {len(resolved)}")
    print(f"  Persistentes (>{n//2} versiones fallando): {len(persistent)}")
    print(f"  Flaky (intermitente): {len(flaky)}")

    print("\n" + "=" * 70)
    print("CASOS PERSISTENTES (fails sistemáticos del modelo)")
    print("=" * 70)
    for cid, fails in sorted(persistent):
        print(f"\n[{cid}] falló en {len(fails)} de {n} versiones")
        # Mostrar última falla
        last = fails[-1]
        print(f"  v={last['version']} status={last['status']}")
        print(f"  reply: {last['reply']}")
        print(f"  tools: {last['tools']}")
        print(f"  reasons: {last['reasons']}")

    print("\n" + "=" * 70)
    print("CASOS FLAKY (regresiones por cambios de auditor/prompt)")
    print("=" * 70)
    for cid, fails in sorted(flaky)[:15]:
        v_list = [f["version"] for f in fails]
        print(f"\n[{cid}] falló en {v_list}")
        last = fails[-1]
        print(f"  v={last['version']} reply: {last['reply'][:120]}")
        print(f"  reasons: {last['reasons']}")

    print("\n" + "=" * 70)
    print("RESUELTOS (pasaban antes, ahora pasan)")
    print("=" * 70)
    for cid, fails in sorted(resolved)[:5]:
        v_list = [f["version"] for f in fails]
        print(f"  [{cid}] falló en {v_list}, ahora PASA en v10-v12")

    # Score evolution
    print("\n" + "=" * 70)
    print("EVOLUCIÓN DE SCORES")
    print("=" * 70)
    for v, d in versions.items():
        if not d:
            continue
        s = d["summary"]
        print(f"  {v}: {s['pass']}/{s['total']} = {s['pass_rate']}%")


if __name__ == "__main__":
    main()
