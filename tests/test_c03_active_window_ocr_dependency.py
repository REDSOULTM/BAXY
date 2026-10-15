"""Both capture producers bind OCR without preauthorizing an unobserved ID."""

import json

import pytest

from baxy_mind.planner import (
    PlannerCatalog,
    PlannerContractError,
    attach_arguments,
    validate_argument_grounding,
    validate_skeleton,
)


_CAPTURE_ID = "capture_0123456789abcdef0123456789abcdef"
_OTHER_CAPTURE_ID = "capture_fedcba9876543210fedcba9876543210"
_OCR_SCHEMA = {
    "type": "object",
    "properties": {"captureId": {"type": "string", "minLength": 1}},
    "required": ["captureId"],
    "additionalProperties": False,
}


@pytest.fixture
def catalog():
    return PlannerCatalog(
        {
            "function": {
                "canonical_name": operation,
                "description": operation,
                "risk": "privacy_sensitive",
                "parameters": _OCR_SCHEMA if operation == "ocr.read" else {
                    "type": "object", "properties": {},
                    "required": [], "additionalProperties": False,
                },
            }
        }
        for operation in (
            "capture.screenshot", "capture.active.window", "ocr.read", "window.active"
        )
    )


def _skeleton(producer, dependencies):
    return {
        "kind": "plan",
        "question": "",
        "steps": [
            {
                "id": "capture",
                "operation": producer,
                "purpose": "Observe the requested surface",
                "dependsOn": [],
                "argumentsMode": "literal",
            },
            {
                "id": "read",
                "operation": "ocr.read",
                "purpose": "Read the observed capture",
                "dependsOn": dependencies,
                "argumentsMode": "after_dependencies",
            },
        ],
    }


@pytest.mark.parametrize("producer", ["capture.screenshot", "capture.active.window"])
def test_each_capture_producer_accepts_deferred_ocr_and_only_observed_id(catalog, producer):
    proposal = validate_skeleton(_skeleton(producer, ["capture"]), catalog, catalog.tools)
    bound = attach_arguments(proposal, {"capture": {}}, catalog)
    assert bound.steps[1].depends_on == ("capture",)
    assert bound.steps[1].arguments_mode == "after_dependencies"
    assert bound.steps[1].arguments is None

    # This grounding function receives trusted observation data, not model prose.
    observed = json.dumps({"captureId": _CAPTURE_ID})
    assert validate_argument_grounding({"captureId": _CAPTURE_ID}, _OCR_SCHEMA, observed)
    assert not validate_argument_grounding(
        {"captureId": _OTHER_CAPTURE_ID}, _OCR_SCHEMA, observed
    )
    assert not validate_argument_grounding({"captureId": _CAPTURE_ID}, _OCR_SCHEMA, "{}")


@pytest.mark.parametrize("producer", ["capture.screenshot", "capture.active.window"])
@pytest.mark.parametrize("dependencies", [[], ["not_observed"]])
def test_present_capture_is_insufficient_without_its_declared_dependency(
    catalog, producer, dependencies
):
    with pytest.raises(PlannerContractError):
        validate_skeleton(_skeleton(producer, dependencies), catalog, catalog.tools)


def test_unrelated_producer_cannot_authorize_ocr(catalog):
    with pytest.raises(PlannerContractError):
        validate_skeleton(_skeleton("window.active", ["capture"]), catalog, catalog.tools)


@pytest.mark.parametrize("producer", ["capture.screenshot", "capture.active.window"])
def test_capture_id_cannot_be_attached_before_producer_is_observed(catalog, producer):
    proposal = validate_skeleton(_skeleton(producer, ["capture"]), catalog, catalog.tools)
    with pytest.raises(PlannerContractError):
        attach_arguments(
            proposal, {"capture": {}, "read": {"captureId": _CAPTURE_ID}}, catalog
        )
