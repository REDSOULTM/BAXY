from __future__ import annotations

import importlib

from baxy_mind.family_classifier import FamilyPrediction


def _module():
    return importlib.import_module(
        "experiments.mind_router_spike.measure_mtop_second_family_recovery"
    )


def test_disagree_addition_fires_when_existing_is_wrong_family() -> None:
    candidate = _module()

    augmented = candidate.disagree_additive_candidates(
        baseline=("task.search",),
        existing_prediction=FamilyPrediction("task", 0.4),
        candidate_prediction=FamilyPrediction("system", 0.5),
        tools_by_family={
            "system": ("system.time", "system.process.list"),
        },
        limit=28,
    )

    assert augmented == ("task.search", "system.time", "system.process.list")


def test_disagree_addition_does_not_fire_when_families_agree() -> None:
    candidate = _module()
    baseline = ("system.time",)

    augmented = candidate.disagree_additive_candidates(
        baseline=baseline,
        existing_prediction=FamilyPrediction("system", 0.4),
        candidate_prediction=FamilyPrediction("system", 0.9),
        tools_by_family={"system": ("system.time", "system.status")},
        limit=28,
    )

    assert augmented == baseline


def test_disagree_addition_never_removes_baseline_candidates() -> None:
    candidate = _module()

    augmented = candidate.disagree_additive_candidates(
        baseline=("audio.status", "audio.mute"),
        existing_prediction=FamilyPrediction("audio", 0.2),
        candidate_prediction=FamilyPrediction("note", 0.8),
        tools_by_family={"note": ("note.create", "note.list", "note.read")},
        limit=3,
    )

    assert augmented[:2] == ("audio.status", "audio.mute")
    assert augmented == ("audio.status", "audio.mute", "note.create")


def test_disagree_addition_fills_abstention() -> None:
    candidate = _module()

    augmented = candidate.disagree_additive_candidates(
        baseline=("web.search",),
        existing_prediction=None,
        candidate_prediction=FamilyPrediction("message", 0.7),
        tools_by_family={"message": ("message.send",)},
        limit=28,
    )

    assert augmented == ("web.search", "message.send")
