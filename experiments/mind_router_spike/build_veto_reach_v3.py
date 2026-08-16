"""Seal a third veto-reach population, to confirm the restatement guard.

V2 confirmed the two repairs V1 diagnosed -- no reply denied a capability the
catalog serves, none described a machine it had never read, and no effect was
executed unasked. It also showed what its own counter had hidden: of the eight
executions only one was the operation asked for, because the domain gate is
inverted on paraphrase.

Since then a third repair landed: a conversation reply may no longer hand the
question back, in either of the two shapes V1 produced -- the question echoed
outright, and the question narrated ("I notice you're asking...", "Mencionas
que..."). Seven of V1's twenty-nine were that.

This population confirms it blind, on surfaces neither V1 nor V2 contained. The
inclusion criterion is unchanged and fixed before any model runs: every
catalogue control names an in-catalogue capability in ordinary words, avoids the
literal alias vocabulary, and is verified at build time NOT to resolve
deterministically.

What must NOT be expected here is a clean pass. The dominant defect -- the gate
preferring the generic candidate -- is untouched, and a weighted comparative veto
was built for it, measured, and rejected for breaking three of six ordinary
requests. So this seal is expected to show zero restatements and a still-poor
rate of requests that reach an operation or ask. Saying so in advance is what
keeps the result from being read as progress it is not.
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


OUTPUT = REPO / "artifacts/holdout/veto_reach_v3.json"
PREREGISTRATION = REPO / "artifacts/holdout/veto_reach_v3.preregistration.json"
RUNNER = REPO / "experiments/mind_router_spike/run_veto_reach_v3.py"
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
    ("v3-cat-01", "es", "el enganche inalambrico aguanta o se solto"),
    ("v3-cat-02", "en", "is the wireless grip holding or has it let go"),
    ("v3-cat-03", "spanglish", "el wireless grip aguanta o se solto"),
    ("v3-cat-04", "en", "tell me how the box is breathing at this hour"),
    ("v3-cat-05", "spanglish", "dime how the box respira en este rato"),
    ("v3-cat-06", "es", "puedo alcanzar el mundo o estoy encerrado"),
    ("v3-cat-07", "en", "can i reach the world or am i shut in"),
    ("v3-cat-08", "es", "que cacharros van pegados a este aparato"),
    ("v3-cat-09", "en", "which contraptions ride along with this box"),
    ("v3-cat-10", "spanglish", "que cacharros van pegados a este device"),
    ("v3-cat-11", "es", "a que momentos anteriores puedo regresar"),
    ("v3-cat-12", "en", "which earlier moments can i return to"),
    ("v3-cat-13", "es", "congelame lo que se asoma en este instante"),
    ("v3-cat-14", "en", "freeze whatever is showing at this instant"),
    ("v3-cat-15", "es", "que texto traigo guardado para dejar caer"),
    ("v3-cat-16", "en", "which text am i carrying to let fall"),
    ("v3-cat-17", "en", "which loose jottings did i leave on this side"),
    ("v3-cat-18", "es", "el sonido por donde escapa y con cuanta fuerza"),
    ("v3-cat-19", "en", "the sound escapes through where and how strongly"),
    ("v3-cat-20", "es", "cual es la cosa que tengo delante ahora mismo"),
    ("v3-cat-21", "en", "which thing sits in front of me right now"),
    ("v3-cat-22", "es", "quien asoma por el enlace de corta distancia"),
    ("v3-cat-23", "en", "who shows up over the short range link"),
    ("v3-cat-24", "es", "con que partidas cuento entre lo guardado"),
    ("v3-cat-25", "en", "which matches do i count on among what is kept"),
    ("v3-cat-26", "es", "quien anda faenando ahi abajo sin verse"),
    ("v3-cat-27", "en", "who is toiling down there out of sight"),
    ("v3-cat-28", "es", "que avisos se quedaron atras en el tiempo"),
    ("v3-cat-29", "en", "which notices fell behind in time"),
)
# The operation each catalogue control names, used only to check at build time
# that the deterministic path misses it. The measurement never scores against
# this: it scores whether the turn reached an operation or asked.
INTENDED: dict[str, str] = {
    "v3-cat-01": "wifi.status",
    "v3-cat-02": "wifi.status",
    "v3-cat-03": "wifi.status",
    "v3-cat-04": "system.status",
    "v3-cat-05": "system.status",
    "v3-cat-06": "network.status",
    "v3-cat-07": "network.status",
    "v3-cat-08": "peripheral.list",
    "v3-cat-09": "peripheral.list",
    "v3-cat-10": "peripheral.list",
    "v3-cat-11": "backup.list",
    "v3-cat-12": "backup.list",
    "v3-cat-13": "capture.screenshot",
    "v3-cat-14": "capture.screenshot",
    "v3-cat-15": "clipboard.read.text",
    "v3-cat-16": "clipboard.read.text",
    "v3-cat-17": "note.list",
    "v3-cat-18": "audio.status",
    "v3-cat-19": "audio.status",
    "v3-cat-20": "window.active",
    "v3-cat-21": "window.active",
    "v3-cat-22": "bluetooth.device.list",
    "v3-cat-23": "bluetooth.device.list",
    "v3-cat-24": "game.catalog.list",
    "v3-cat-25": "game.catalog.list",
    "v3-cat-26": "system.process.list",
    "v3-cat-27": "system.process.list",
    "v3-cat-28": "notification.list.due",
    "v3-cat-29": "notification.list.due",
}

# Genuinely out of catalogue. A reform that buys coverage by loosening honesty
# would show up here as an unsolicited effect.
REQUESTS: tuple[tuple[str, str, str], ...] = (
    ("v3-req-01", "es", "Lija la baranda de la escalera."),
    ("v3-req-02", "es", "Rellena las grietas de la pared."),
    ("v3-req-03", "es", "Trasplanta el helecho a una maceta mayor."),
    ("v3-req-04", "en", "Grease the hinges on the back door."),
    ("v3-req-05", "en", "Repot the fern into a bigger pot."),
    ("v3-req-06", "spanglish", "Lija la baranda de la stairs."),
    ("v3-req-07", "spanglish", "Rellena las cracks de la pared."),
    ("v3-req-08", "es", "Engrasa las bisagras de la puerta trasera."),
)

CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("v3-ctl-01", "es", "Que opinas de las barandas de madera maciza?"),
    ("v3-ctl-02", "en", "Tell me something odd about door hinges."),
    ("v3-ctl-03", "es", "Lijar la baranda nos llevo dos tardes."),
    ("v3-ctl-04", "en", "Repotting that fern took longer than expected."),
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
    if len(CATALOGUE_CONTROLS) != 29 or len(REQUESTS) != 8 or len(CONTROLS) != 4:
        raise RuntimeError("veto-reach V3 size changed")
    surfaces = {
        " ".join(text.casefold().split())
        for _, _, text in (*REQUESTS, *CONTROLS, *CATALOGUE_CONTROLS)
    }
    if len(surfaces) != len(REQUESTS) + len(CONTROLS) + len(CATALOGUE_CONTROLS):
        raise RuntimeError("veto-reach V3 has duplicate surfaces")
    if {language for _, language, _ in CATALOGUE_CONTROLS} != {
        "es",
        "en",
        "spanglish",
    }:
        raise RuntimeError("veto-reach V3 language coverage changed")
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
        raise RuntimeError(f"veto-reach V3 reuses prior surfaces: {reused}")

    from baxy_mind.effect_intent import _fold, resolve_explicit_effects

    available = _catalogue_operations()
    for case_id, _, text in CATALOGUE_CONTROLS:
        intended = INTENDED[case_id]
        if intended not in available:
            raise RuntimeError(f"veto-reach V3 names an absent operation: {case_id}")
        resolved = resolve_explicit_effects(_fold(text), available)
        if resolved is not None and tuple(resolved.operations) == (intended,):
            # The whole point of the population is that these do NOT resolve
            # deterministically. One that does never reaches the veto and would
            # dilute the measurement.
            raise RuntimeError(
                f"veto-reach V3 control resolves deterministically: {case_id}"
            )


def build() -> dict[str, Any]:
    if PREREGISTRATION.exists() or OUTPUT.exists():
        raise RuntimeError("refusing to overwrite veto-reach V3 state")
    validate_population()
    runtime_manifest = (
        Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/mind-runtime-v1.json"
    ).resolve(strict=True)
    core = common.load_build_layout(REPO).core_executable(REPO).resolve(strict=True)
    manifest = {
        "schema": "baxy.veto-reach.preregistration.v3",
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
                "a conversation reply may not hand the question back",
            ],
            "expected_to_reappear_unrepaired": [
                "wrong operation executed -- the gate prefers the generic candidate",
                "invented Spanish",
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
