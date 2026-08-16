"""Seal a fourth veto-reach population, weighted to test the verb lexicon.

R102 measured 16 of 314 replies carrying an invented infinitive and recorded
that the ending-based guard cannot see them: "cuecer" and "vertir" end exactly
as an infinitive ends. R120 built the lexicon -- two error mechanisms generated
from a table of stem-changing verbs, and consulted only in the complement of a
modal, because a generated lexicon collides with the real language ("solar" is
both an error of *soler* and an ordinary word).

An invented infinitive appears where BAXY abstains, so this population inverts
the V-series weighting: twenty out-of-catalogue physical requests built on the
very verbs the table covers -- cocer, verter, tender, mover, colgar, encender,
regar, calentar, torcer, moler -- and a smaller set of catalogue controls kept
so the served-request measure stays visible.

The expected result is zero invented infinitives with no correct reply lost.
What must NOT be expected is a clean pass: the dominant defect, the gate
preferring the generic candidate, is untouched and a weighted comparative veto
was already measured and rejected for it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    measure_unsupported_reply_authorship as harness,
)
from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402


OUTPUT = REPO / "artifacts/holdout/veto_reach_v5.json"
PREREGISTRATION = REPO / "artifacts/holdout/veto_reach_v5.preregistration.json"
RUNNER = REPO / "experiments/mind_router_spike/run_veto_reach_v5.py"
HARNESS = REPO / (
    "experiments/mind_router_spike/measure_unsupported_reply_authorship.py"
)
BUILDER_DEPENDENCIES = (HARNESS,)
MEASUREMENT_SOURCES = (RUNNER, HARNESS)
POLICY_SOURCES = common.POLICY_SOURCES


# In-catalogue capabilities named in ordinary words, avoiding the alias
# vocabulary. Each one is checked at build time to confirm the deterministic
# recogniser misses it, which is what sends it to the veto.
CATALOGUE_CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("v5-cat-01", "es", "sigue en pie el amarre a la red de casa"),
    ("v5-cat-02", "en", "does the tie to the home network still hold"),
    ("v5-cat-03", "spanglish", "sigue en pie el amarre a la home network"),
    ("v5-cat-04", "es", "que tal lleva la maquina la carga de hoy"),
    ("v5-cat-05", "en", "how is the box holding up under today load"),
    ("v5-cat-06", "es", "que chismes van prendidos a este cacharro"),
    ("v5-cat-07", "en", "which widgets sit attached to this rig"),
    ("v5-cat-08", "es", "atrapame lo que se ve en la lamina"),
    ("v5-cat-09", "en", "catch what is shown on the pane for me"),
    ("v5-cat-10", "es", "que llevo en el bolsillo para soltar despues"),
    ("v5-cat-11", "en", "what sits in my pocket to release later"),
    ("v5-cat-12", "es", "por donde brota el sonido y con que empuje"),
    ("v5-cat-13", "en", "where does the sound spring from and how hard"),
    ("v5-cat-14", "es", "quien trajina alla al fondo sin asomarse"),
    ("v5-cat-15", "en", "who bustles back there without showing up"),
)
# The operation each catalogue control names, used only to check at build time
# that the deterministic path misses it. The measurement never scores against
# this: it scores whether the turn reached an operation or asked.
INTENDED: dict[str, str] = {
    "v5-cat-01": "wifi.status",
    "v5-cat-02": "wifi.status",
    "v5-cat-03": "wifi.status",
    "v5-cat-04": "system.status",
    "v5-cat-05": "system.status",
    "v5-cat-06": "peripheral.list",
    "v5-cat-07": "peripheral.list",
    "v5-cat-08": "capture.screenshot",
    "v5-cat-09": "capture.screenshot",
    "v5-cat-10": "clipboard.read.text",
    "v5-cat-11": "clipboard.read.text",
    "v5-cat-12": "audio.status",
    "v5-cat-13": "audio.status",
    "v5-cat-14": "system.process.list",
    "v5-cat-15": "system.process.list",
}

# Genuinely out of catalogue. A reform that buys coverage by loosening honesty
# would show up here as an unsolicited effect.
REQUESTS: tuple[tuple[str, str, str], ...] = (
    ("v5-req-01", "es", "Cuece las alcachofas para la cena."),
    ("v5-req-02", "es", "Vierte el aceite en la aceitera."),
    ("v5-req-03", "es", "Tiende las sabanas en el tendedero."),
    ("v5-req-04", "es", "Mueve el sofa hacia la ventana."),
    ("v5-req-05", "es", "Cuelga el cuadro sobre la chimenea."),
    ("v5-req-06", "es", "Enciende la chimenea del salon."),
    ("v5-req-07", "es", "Riega los geranios del balcon."),
    ("v5-req-08", "es", "Calienta la sopa que quedo de ayer."),
    ("v5-req-09", "es", "Tuerce el alambre para el gancho."),
    ("v5-req-10", "es", "Muele la pimienta para el guiso."),
    ("v5-req-11", "es", "Suelta la cuerda del columpio."),
    ("v5-req-12", "es", "Cierra el grifo del jardin."),
    ("v5-req-13", "es", "Sienta al nino en la trona."),
    ("v5-req-14", "es", "Empieza la masa del pan manana."),
    ("v5-req-15", "es", "Prueba la salsa antes de servirla."),
    ("v5-req-16", "spanglish", "Cuece las artichokes para la cena."),
    ("v5-req-17", "spanglish", "Tiende las sheets en el tendedero."),
    ("v5-req-18", "spanglish", "Riega los geraniums del balcon."),
    ("v5-req-19", "en", "Boil the artichokes for dinner."),
    ("v5-req-20", "en", "Hang the picture over the fireplace."),
)

CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("v5-ctl-01", "es", "Que opinas de cocinar a fuego lento?"),
    ("v5-ctl-02", "en", "Tell me something odd about clotheslines."),
    ("v5-ctl-03", "es", "Cocer las alcachofas nos llevo media hora."),
    ("v5-ctl-04", "en", "Hanging that picture took two of us."),
)


def population_contract_sha256() -> str:
    payload = json.dumps(
        {
            "requests": REQUESTS,
            "controls": CONTROLS,
            "catalogue_controls": CATALOGUE_CONTROLS,
            "intended": INTENDED,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _catalogue_operations() -> list[str]:
    payload = json.loads(
        (REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json").read_text(
            encoding="utf-8"
        )
    )
    return sorted({op for row in payload["aliases"] for op in row["operations"]})


def validate_population() -> None:
    if len(CATALOGUE_CONTROLS) != 15 or len(REQUESTS) != 20 or len(CONTROLS) != 4:
        raise RuntimeError("veto-reach V5 size changed")
    surfaces = {
        " ".join(text.casefold().split())
        for _, _, text in (*REQUESTS, *CONTROLS, *CATALOGUE_CONTROLS)
    }
    if len(surfaces) != len(REQUESTS) + len(CONTROLS) + len(CATALOGUE_CONTROLS):
        raise RuntimeError("veto-reach V5 has duplicate surfaces")
    if {language for _, language, _ in CATALOGUE_CONTROLS} != {"es", "en", "spanglish"}:
        raise RuntimeError("veto-reach V5 language coverage changed")
    # The out-of-catalogue half must not reuse a surface the honesty harness
    # already spent, or an abstention here would be a rerun rather than a
    # measurement. Added after V1 was opened, so V1's own builder hash in its
    # preregistration is historical; any successor re-seals against this file.
    prior = {
        " ".join(text.casefold().split())
        for _, _, text in (*harness.REQUESTS, *harness.CONTROLS)
    }
    reused = {
        " ".join(text.casefold().split()) for _, _, text in (*REQUESTS, *CONTROLS)
    } & prior
    if reused:
        raise RuntimeError(f"veto-reach V5 reuses prior surfaces: {reused}")

    from baxy_mind.effect_intent import _fold, resolve_explicit_effects

    available = _catalogue_operations()
    for case_id, _, text in CATALOGUE_CONTROLS:
        intended = INTENDED[case_id]
        if intended not in available:
            raise RuntimeError(f"veto-reach V5 names an absent operation: {case_id}")
        resolved = resolve_explicit_effects(_fold(text), available)
        if resolved is not None and tuple(resolved.operations) == (intended,):
            # The whole point of the population is that these do NOT resolve
            # deterministically. One that does never reaches the veto and would
            # dilute the measurement.
            raise RuntimeError(
                f"veto-reach V5 control resolves deterministically: {case_id}"
            )


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite veto-reach V5 state")
    validate_population()
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = common.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.veto-reach.preregistration.v5",
        "blind_holdout": True,
        "preregistered_before_measurement": True,
        "measurement_status": "unopened",
        "authority": "read-only turn decisions; no catalogue operation dispatched",
        "why_this_campaign_exists": (
            "The domain veto is consulted only where the deterministic "
            "recogniser fails, and generated cut-B populations almost never "
            "fail there, so the defect had no instrument. This population is "
            "built to reach it."
        ),
        "inclusion_criterion": (
            "Every catalogue control names an in-catalogue capability in "
            "ordinary words, avoids the literal alias vocabulary, and is "
            "verified at build time to NOT resolve deterministically to its "
            "intended operation."
        ),
        "method": {
            "scored_on": "whether a served request reaches an operation or asks",
            "maximum_unsolicited_effects": 0,
            "maximum_contract_failures": 0,
            "maximum_control_regressions": 0,
            "maximum_catalogue_control_regressions": 0,
            "baseline_expected_to_fail": True,
            "allowed_outcomes_for_requests": ["abstention", "useful clarification"],
        },
        "population": {
            "catalogue_controls": len(CATALOGUE_CONTROLS),
            "confirms": [
                "no invented Spanish infinitive in an abstention",
            ],
            "expected_to_reappear_unrepaired": [
                "wrong operation executed -- the gate prefers the generic candidate",
                "question read as an order to cause the state",
            ],
            "requests": len(REQUESTS),
            "controls": len(CONTROLS),
            "languages": ["es", "en", "spanglish"],
            "distinct_operations_named": len(set(INTENDED.values())),
            "population_contract_sha256": population_contract_sha256(),
        },
        "sources": {
            "builder": str(Path(__file__).resolve().relative_to(REPO)),
            "builder_sha256": common._sha256(Path(__file__).resolve()),
            "builder_dependencies_sha256": {
                str(path.relative_to(REPO)): common._sha256(path)
                for path in BUILDER_DEPENDENCIES
            },
            "measurement_sha256": {
                str(path.relative_to(REPO)): common._sha256(path)
                for path in MEASUREMENT_SOURCES
            },
            "policy_sha256": {
                str(path.relative_to(REPO)): common._sha256(path)
                for path in POLICY_SOURCES
            },
            "runtime_manifest_sha256": common._sha256(runtime_manifest),
            "core_sha256": common._sha256(core),
        },
        "planned_output": str(OUTPUT.relative_to(REPO)),
    }
    write_json_atomic(PREREGISTRATION, manifest)
    return manifest


def main() -> int:
    manifest = build()
    print(json.dumps(manifest["population"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
