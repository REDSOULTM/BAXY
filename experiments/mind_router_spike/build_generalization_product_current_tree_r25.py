"""Re-seal R24's never-opened Cut-B population with the measurement code final.

R24 was sealed before its measurement code was finished. Its preregistration
binds ``tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs``, and
the twelve private-memory rows of any such population are exercised by an NUnit
method that has to exist in that file -- so the method was added *after* the
seal, and the probe refused to open it: "measurement code changed after
preregistration". The builder then refused to overwrite the sealed state.

Both refusals are correct and neither is argued past here. The guard exists so
that "my edit was harmless" is never the thing standing between a corpus and
its result, and re-pointing it at my own judgement would be closing a defect by
relabelling it.

So R24 is void and stays on disk, unopened. This population is **identical to
R24's**, which costs nothing: R24 was never measured, so its surfaces have
never been seen by the system and are still blind. It is therefore deliberately
excluded from PRIOR_CORPORA below -- the overlap check must compare against
what the system has *seen*, and it has seen nothing of R24. The only difference
between the two seals is that this one binds the measurement code as it will
actually run.

The population's own design is unchanged from R24: four instruction frames per
language instead of one, and a vocative that carries no instruction noun, so
that a single missing word costs at most a quarter of a cell. R23 lost a whole
Spanish cell to the word ``indicacion`` and that must not be repeatable.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_generalization_product_current_tree_r24 as r24,
)
from scripts import build_generalization_product_holdout_r3 as builder  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/generalization_product_current_tree_r25.jsonl"
PREREGISTRATION = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r25.preregistration.json"
)
MIND_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r25_mind.json"
)
MIND_AUDIT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r25_mind.raw.jsonl"
)
MEMORY_TRX = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r25_memory.trx"
)
PRODUCT_OUTPUT = REPO / (
    "artifacts/holdout/generalization_product_current_tree_r25_product.json"
)
# R24 is deliberately absent: it was never opened, so none of its surfaces have
# been seen and there is nothing for the overlap check to protect against.
PRIOR_CORPORA = r24.PRIOR_CORPORA
POLICY_SOURCES = r24.POLICY_SOURCES
MEASUREMENT_SOURCES = (
    REPO / "experiments/mind_router_spike/"
    "probe_generalization_product_current_tree_r25.py",
    REPO / "experiments/mind_router_spike/"
    "analyze_generalization_product_current_tree_r25.py",
    REPO / "experiments/mind_router_spike/probe_generalization_product_holdout_r2.py",
    REPO / "experiments/mind_router_spike/analyze_generalization_product_holdout_r2.py",
    REPO / "scripts/measure_mind_budget.py",
    REPO / "scripts/baxy_runtime_config.py",
    REPO / "tests/Baxy.Integration.Tests/NaturalMemoryRequestParserTests.cs",
)
BUILDER_DEPENDENCIES = (
    *r24.BUILDER_DEPENDENCIES,
    Path(r24.__file__).resolve(),
)
REFERENCES = r24.REFERENCES


def configure() -> None:
    builder.OUTPUT = OUTPUT
    builder.PREREGISTRATION = PREREGISTRATION
    builder.MIND_OUTPUT = MIND_OUTPUT
    builder.MIND_AUDIT = MIND_AUDIT
    builder.MEMORY_TRX = MEMORY_TRX
    builder.PRODUCT_OUTPUT = PRODUCT_OUTPUT
    builder.PRIOR_CORPORA = PRIOR_CORPORA
    builder.POLICY_SOURCES = POLICY_SOURCES
    builder.MEASUREMENT_SOURCES = MEASUREMENT_SOURCES
    builder.BUILDER_DEPENDENCIES = BUILDER_DEPENDENCIES
    builder.CAMPAIGN = "current-tree-r25"
    builder.BUILDER_SOURCE = Path(__file__).resolve()
    builder.ROW_SCHEMA = "baxy.generalization-product-current-tree.r25"
    builder.PREREGISTRATION_SCHEMA = (
        "baxy.generalization-product-current-tree-preregistration.r25"
    )
    builder.EXPECTED_POPULATION = 700
    builder.MINIMUM_CASES = 700
    builder.METHOD_DESCRIPTION = (
        "reseal_of_the_never_opened_r24_population_with_the_measurement_code_"
        "final_four_rotating_instruction_nouns_per_language_and_an_instruction_"
        "free_vocative"
    )
    builder.REFERENCES = REFERENCES
    builder.ADDRESSED_PREFIXES = {
        "es": "Baxy, ",
        "en": "Baxy, ",
        "spanglish": "Baxy, ",
    }
    builder.SCENARIOS = r24.SCENARIOS
    builder.CLARIFICATIONS = r24.CLARIFICATIONS
    builder.COMPOSITIONS = r24.COMPOSITIONS
    builder.CONVERSATIONS = r24.CONVERSATIONS


def main() -> int:
    configure()
    return builder.main()


if __name__ == "__main__":
    raise SystemExit(main())
