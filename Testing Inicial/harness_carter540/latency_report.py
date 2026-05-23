"""Reporte de latencias por categoria desde un merged JSON."""
import argparse
import json
from pathlib import Path


def percentiles(values):
    if not values:
        return (0, 0, 0, 0, 0)
    s = sorted(values)
    def p(k):
        return s[min(int(k * (len(s) - 1)), len(s) - 1)]
    return p(0.5), p(0.9), p(0.99), max(s), sum(s)/len(s)


CAT_NAMES = {
    1: "Saludos", 2: "Identidad", 3: "Conocimiento",
    4: "Memoria", 5: "Apps duales", 6: "Sistema",
    7: "Apps", 8: "Web", 9: "Steam",
    10: "Filesystem", 11: "Terminal", 12: "Destructive",
    13: "GUI", 14: "Multi-step", 15: "Typos",
    16: "Phonetic", 17: "Conversación", 18: "Multi-turn",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    d = json.loads(Path(args.input).read_text(encoding="utf-8"))
    by_cat = {}
    all_lat = []
    for r in d["results"]:
        cat = r.get("category")
        lat = r.get("latency_ms", 0)
        if lat <= 0:
            continue
        by_cat.setdefault(cat, []).append(lat)
        all_lat.append(lat)

    print(f"\n{'Cat':<5} {'Nombre':<14} {'n':<3} {'p50':>7} {'p90':>7} {'p99':>7} {'max':>7} {'avg':>7}")
    print("-" * 70)
    for cat in sorted(by_cat.keys()):
        p50, p90, p99, mx, avg = percentiles(by_cat[cat])
        name = CAT_NAMES.get(cat, "?")
        print(f"C{cat:02d}   {name:<14} {len(by_cat[cat]):<3} {p50/1000:>6.2f}s {p90/1000:>6.2f}s {p99/1000:>6.2f}s {mx/1000:>6.2f}s {avg/1000:>6.2f}s")

    p50, p90, p99, mx, avg = percentiles(all_lat)
    print("-" * 70)
    print(f"GLOBAL{' '*8} {len(all_lat):<3} {p50/1000:>6.2f}s {p90/1000:>6.2f}s {p99/1000:>6.2f}s {mx/1000:>6.2f}s {avg/1000:>6.2f}s")

    # Alexa-tier check (Carter contract: <5s trivial, <8s tool simple, <15s app open, <20s multi-step)
    print("\n=== ALEXA-TIER CHECK (Carter Contract) ===")
    trivial = []
    for cat in (1, 2, 3, 15, 16, 17, 18):
        trivial.extend(by_cat.get(cat, []))
    tool_simple = []
    for cat in (4, 5, 6, 11, 12):
        tool_simple.extend(by_cat.get(cat, []))
    app_open = []
    for cat in (7, 8, 9):
        app_open.extend(by_cat.get(cat, []))
    multi_step = []
    for cat in (10, 13, 14):
        multi_step.extend(by_cat.get(cat, []))

    for label, vals, target_p99 in [
        ("Trivial (cat 1,2,3,15-18)", trivial, 5000),
        ("Tool simple (cat 4-6,11,12)", tool_simple, 8000),
        ("App open (cat 7,8,9)", app_open, 15000),
        ("Multi-step (cat 10,13,14)", multi_step, 20000),
    ]:
        if vals:
            p50, p90, p99, mx, avg = percentiles(vals)
            ok99 = "OK" if p99 <= target_p99 else "FAIL"
            print(f"  {label:<32} n={len(vals):<3} p50={p50/1000:.2f}s p90={p90/1000:.2f}s p99={p99/1000:.2f}s [{ok99}] (target p99 <{target_p99/1000}s)")


if __name__ == "__main__":
    main()
