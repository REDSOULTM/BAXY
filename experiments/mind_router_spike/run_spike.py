"""Spike de de-riesgo: router de intención por embeddings vs oráculos congelados.

Dos preguntas separadas, dos modos:

- `--eval-coverage`: pools = anclas autoradas + textos positivos curados del
  propio corpus (la configuración de producción; el regex fue escrito contra
  esos mismos textos, así que esta comparación es de igual a igual). Mide
  cobertura: positivos deben enrutar y negativos deben abstenerse.
- `--eval-loo`: mismo banco de exemplars, pero al consultar se enmascara todo
  exemplar cuyo texto normalizado sea idéntico al del caso evaluado
  (leave-one-out). Mide generalización a fraseos no vistos literalmente —
  capacidad que el regex no tiene (≈0 % fuera de sus patrones).

Umbrales congelados con `--dev` (dev_probes.py, autoría propia disjunta)
ANTES de tocar los oráculos.

Router: score(clase) = máx coseno contra su pool; se abstiene si gana un pool
ABSTAIN__*, si best < tau o si (best - second) < margen. Fail-closed.

Scoring:
- Positivos: correcto si predicción == etiqueta exacta (scope incluido).
- ABSTAIN: correcto si el router se abstiene.
- ABSTAIN_POLICY (negativos de memoria): correcto si abstiene o enruta a
  memory.* (la política de confirmación vive en la capa determinista de
  memoria); se reporta desglosado.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "src"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SRC))

from baxy_mind.tools.frozen_files import verify_frozen_file  # noqa: E402

PROTOCOL = HERE / "tournament_encoder_protocol.json"
CASES = verify_frozen_file(REPO, PROTOCOL, "router_cases")
verify_frozen_file(REPO, PROTOCOL, "router_bank_sources")
verify_frozen_file(REPO, PROTOCOL, "development_probes")

from baxy_mind.tools.router_bank_sources import ALL_POOLS  # noqa: E402

MODEL_NAME = "intfloat/multilingual-e5-small"
QUERY_PREFIX = "query: "


def configure(model_name: str | None, prefix: str | None) -> None:
    global MODEL_NAME, QUERY_PREFIX
    if model_name is not None:
        MODEL_NAME = model_name
    if prefix is not None:
        QUERY_PREFIX = prefix


def normalize(text: str) -> str:
    """Clave agresiva (sin tildes) SOLO para el guard de contaminación."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(stripped.split())


def identity_key(text: str) -> str:
    """Clave de identidad para dedup/LOO. CONSERVA tildes: una tilde puede
    invertir la polaridad (imperativo «silencie» vs pasado «silencié»)."""
    return " ".join(unicodedata.normalize("NFC", text.casefold()).split())


def load_cases() -> list[dict]:
    with CASES.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def assert_authored_disjoint(cases: list[dict]) -> None:
    """Las anclas autoradas no pueden duplicar textos del oráculo."""
    oracle_texts = {normalize(case["text"]) for case in cases}
    collisions = [
        (name, exemplar)
        for name, exemplars in ALL_POOLS.items()
        for exemplar in exemplars
        if normalize(exemplar) in oracle_texts
    ]
    if collisions:
        raise SystemExit(f"CONTAMINACION pool/oráculo: {collisions}")


def corpus_exemplars(cases: list[dict]) -> list[tuple[str, str]]:
    """(etiqueta, texto) del corpus curado completo, dedup por texto.

    Positivos con su operación; negativos duros como clase ABSTAIN__corpus
    (el banco de producción aprende del ledger entero, igual que el regex fue
    escrito contra él). Un texto con más de una etiqueta se excluye.
    Los ABSTAIN_POLICY no se agregan: su intención sí es memory.* y la política
    vive en la capa determinista.
    """
    by_text: dict[str, set[str]] = defaultdict(set)
    text_of: dict[str, str] = {}
    for case in cases:
        if case["label"] == "ABSTAIN_POLICY":
            continue
        label = "ABSTAIN__corpus" if case["label"] == "ABSTAIN" else case["label"]
        key = identity_key(case["text"])
        by_text[key].add(label)
        text_of[key] = case["text"]
    return [
        (labels.copy().pop(), text_of[key])
        for key, labels in by_text.items()
        if len(labels) == 1
    ]


class EmbeddingRouter:
    def __init__(self, extra: list[tuple[str, str]] | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(MODEL_NAME, device="cpu")
        self.class_names: list[str] = []
        class_index_of: dict[str, int] = {}
        self.class_of_row: list[int] = []
        self.norm_of_row: list[str] = []
        sentences: list[str] = []

        def add(label: str, text: str) -> None:
            if label not in class_index_of:
                class_index_of[label] = len(self.class_names)
                self.class_names.append(label)
            sentences.append(QUERY_PREFIX + text)
            self.class_of_row.append(class_index_of[label])
            self.norm_of_row.append(identity_key(text))

        for name, exemplars in ALL_POOLS.items():
            for exemplar in exemplars:
                add(name, exemplar)
        for label, text in extra or []:
            add(label, text)

        self.pool_matrix = self.model.encode(
            sentences, normalize_embeddings=True, show_progress_bar=False
        )

    def route_batch(
        self,
        texts: list[str],
        tau: float,
        margin: float,
        leave_one_out: bool = False,
    ) -> list[tuple[str, float, float, str]]:
        import numpy as np

        queries = self.model.encode(
            [QUERY_PREFIX + text for text in texts],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        sims = queries @ self.pool_matrix.T
        if leave_one_out:
            norms = np.array(self.norm_of_row)
            for i, text in enumerate(texts):
                sims[i, norms == identity_key(text)] = -1.0

        rows_by_class = defaultdict(list)
        for row, class_index in enumerate(self.class_of_row):
            rows_by_class[class_index].append(row)
        class_scores = np.stack(
            [
                sims[:, rows_by_class[class_index]].max(axis=1)
                for class_index in range(len(self.class_names))
            ],
            axis=1,
        )
        results = []
        order = np.argsort(-class_scores, axis=1)
        for i in range(len(texts)):
            best_index = int(order[i, 0])
            best = float(class_scores[i, best_index])
            second = float(class_scores[i, int(order[i, 1])])
            winner = self.class_names[best_index]
            if winner.startswith("ABSTAIN__"):
                prediction = "ABSTAIN"
            elif best < tau or (best - second) < margin:
                prediction = "ABSTAIN"
            else:
                prediction = winner
            results.append((prediction, best, best - second, winner))
        return results


def is_correct(case: dict, prediction: str) -> bool:
    label = case["label"]
    if label == "ABSTAIN":
        return prediction == "ABSTAIN"
    if label == "ABSTAIN_POLICY":
        return prediction == "ABSTAIN" or prediction.startswith("memory.")
    return prediction == label


def run_dev() -> None:
    from dev_probes import DEV_PROBES

    router = EmbeddingRouter()
    texts = [text for text, _ in DEV_PROBES]
    best_config = None
    for tau_pct in range(80, 95):
        tau = tau_pct / 100
        for margin_pct in range(0, 6):
            margin = margin_pct / 200
            results = router.route_batch(texts, tau, margin)
            wrong = sum(
                1
                for (prediction, *_), (_, expected) in zip(results, DEV_PROBES)
                if expected != "ABSTAIN"
                and prediction not in ("ABSTAIN", expected)
            )
            false_route = sum(
                1
                for (prediction, *_), (_, expected) in zip(results, DEV_PROBES)
                if expected == "ABSTAIN" and prediction != "ABSTAIN"
            )
            missed = sum(
                1
                for (prediction, *_), (_, expected) in zip(results, DEV_PROBES)
                if expected != "ABSTAIN" and prediction == "ABSTAIN"
            )
            cost = 3 * (wrong + false_route) + missed
            if best_config is None or cost < best_config[0]:
                best_config = (cost, tau, margin, wrong, false_route, missed)
    cost, tau, margin, wrong, false_route, missed = best_config
    print(
        json.dumps(
            {
                "frozen_tau": tau,
                "frozen_margin": margin,
                "dev_cost": cost,
                "dev_wrong_route": wrong,
                "dev_false_route_on_distractor": false_route,
                "dev_over_abstention": missed,
                "dev_size": len(DEV_PROBES),
            },
            indent=2,
        )
    )


def run_eval(mode: str, tau: float, margin: float) -> None:
    cases = load_cases()
    assert_authored_disjoint(cases)
    extra = corpus_exemplars(cases)
    leave_one_out = mode == "loo"
    router = EmbeddingRouter(extra=extra)

    start = time.perf_counter()
    results = router.route_batch(
        [case["text"] for case in cases], tau, margin, leave_one_out=leave_one_out
    )
    elapsed = time.perf_counter() - start

    per_set: dict[str, Counter] = defaultdict(Counter)
    confusion: Counter = Counter()
    failures: list[dict] = []
    danger = Counter()
    for case, (prediction, best, delta, winner) in zip(cases, results):
        correct = is_correct(case, prediction)
        if not correct:
            if prediction == "ABSTAIN":
                danger["safe_over_abstention"] += 1
            else:
                danger["dangerous_wrong_or_false_route"] += 1
        per_set[case["set"]]["total"] += 1
        per_set[case["set"]]["correct" if correct else "wrong"] += 1
        confusion[(case["label"], prediction)] += 1
        if not correct:
            failures.append(
                {
                    "set": case["set"],
                    "message_id": case["message_id"],
                    "text": case["text"],
                    "expected": case["label"],
                    "predicted": prediction,
                    "winner_pool": winner,
                    "best_score": round(best, 4),
                    "margin": round(delta, 4),
                    "category": case.get("category"),
                }
            )

    sample = [case["text"] for case in cases[:: max(1, len(cases) // 50)]][:50]
    lat_start = time.perf_counter()
    for text in sample:
        router.route_batch([text], tau, margin)
    single_ms = (time.perf_counter() - lat_start) / len(sample) * 1000

    import psutil

    ram_mib = psutil.Process().memory_info().rss / (1024 * 1024)
    weights_mib = None
    try:
        from huggingface_hub import snapshot_download

        snap = Path(snapshot_download(MODEL_NAME, local_files_only=True))
        weights_mib = sum(
            f.stat().st_size for f in snap.rglob("*") if f.is_file()
        ) / (1024 * 1024)
    except Exception:
        pass

    report = {
        "protocol": f"mind-router-spike-v2-{mode}",
        "model": MODEL_NAME,
        "frozen_tau": tau,
        "frozen_margin": margin,
        "corpus_exemplars": len(extra),
        "total_cases": len(cases),
        "per_set": {
            name: {
                "total": counts["total"],
                "correct": counts["correct"],
                "accuracy": round(counts["correct"] / counts["total"], 4),
            }
            for name, counts in sorted(per_set.items())
        },
        "overall_accuracy": round(
            sum(counts["correct"] for counts in per_set.values()) / len(cases), 4
        ),
        "regex_baseline": {
            "coverage": "100% en sets congelados por construcción (tests .NET verdes)",
            "generalization": "≈0% fuera de patrones literales; sin capacidad semántica",
        },
        "failure_modes": dict(danger),
        "process_ram_mib": round(ram_mib, 1),
        "weights_size_mib": round(weights_mib, 1) if weights_mib else None,
        "batch_seconds": round(elapsed, 2),
        "single_query_cpu_ms": round(single_ms, 1),
        "confusion": [
            {"expected": expected, "predicted": predicted, "count": count}
            for (expected, predicted), count in sorted(
                confusion.items(), key=lambda item: -item[1]
            )
        ],
        "failures": failures,
    }
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    slug = MODEL_NAME.replace("/", "__")
    out_path = out_dir / f"report_{mode}__{slug}.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        key: report[key]
        for key in (
            "protocol",
            "per_set",
            "overall_accuracy",
            "failure_modes",
            "single_query_cpu_ms",
        )
    }
    summary["failure_count"] = len(failures)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"reporte completo -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--eval-coverage", action="store_true")
    parser.add_argument("--eval-loo", action="store_true")
    parser.add_argument("--tau", type=float)
    parser.add_argument("--margin", type=float)
    parser.add_argument("--model", type=str)
    parser.add_argument("--prefix", type=str)
    args = parser.parse_args()
    configure(args.model, args.prefix)
    if args.dev:
        run_dev()
        return
    if not (args.eval_coverage or args.eval_loo):
        raise SystemExit("usar --dev, --eval-coverage o --eval-loo")
    if args.tau is None or args.margin is None:
        raise SystemExit("las corridas de eval exigen --tau y --margin congelados")
    if args.eval_coverage:
        run_eval("coverage", args.tau, args.margin)
    if args.eval_loo:
        run_eval("loo", args.tau, args.margin)


if __name__ == "__main__":
    main()
