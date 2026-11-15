"""Rule «update_up_to_date», INT36G (VIVO21, 3 of 3: «¿estás al día?» with 1.5.3 installed and 1.5.2 the latest
published was answered «estoy desactualizado»; the receipt said installed 1.5.3, latest 1.5.2, newer false). BAXY told
out of date, or a newer version there, in a turn whose own baxy.update found nothing newer than the installed one: the
fact goes back to the model, as update_early's. Read in Spanish and English; never beside a newer version."""
import json

from baxy_mind.answer_check import check

SAID = "BAXY 1.5.3 is installed, newer than 1.5.2, the latest version published: BAXY is up to date and there is nothing to update"


def _receipt(latest: str, newer: bool, action: str = "check") -> dict:
    observed = {"version": 1, "channel": "github", "installed": "1.5.3", "checked": True, "updatedBy": "github",
                "latest": latest, "newer": newer, **({} if newer else {"upToDate": SAID})}
    failed = action == "install" and not newer
    return {"op": "baxy.update", "tool": "baxy_update", "arguments": {"action": action}, "observation": json.dumps(
        {"status": "failed", "error": "baxy_update_already_latest", "observed": observed} if failed
        else {"status": "completed", "verification": "readback", "observed": observed}),
        "outcome": "falló" if failed else "completado y verificado", "completed": not failed, "read": True}


def _found(answer: str, receipts: list[dict], request: str = "¿estás al día?") -> list[dict]:
    session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return [f for f in check(answer, request, receipts, session) if f["rule"] == "update_up_to_date"]


def test_out_of_date_said_when_the_installed_one_is_newer_is_found() -> None:
    for answer in ("Estoy desactualizado: la última versión es la 1.5.2.", "No estoy al día, tengo la 1.5.3.",
                   "Hay una versión más nueva disponible, la 1.5.2.", "I'm out of date: the latest is 1.5.2.",
                   "There is a newer version, 1.5.2.", "You're not up to date."):
        found = _found(answer, [_receipt("1.5.2", False)])
        assert [f["rule"] for f in found] == ["update_up_to_date"], answer
        assert "1.5.3" in found[0]["fact"] and "1.5.2" in found[0]["fact"] and "al día" in found[0]["fact"], answer


def test_out_of_date_said_when_they_are_the_same_is_found() -> None:
    found = _found("Estoy desactualizada.", [_receipt("1.5.3", False)])
    assert [f["rule"] for f in found] == ["update_up_to_date"]
    assert _found("Estoy desactualizada.", [_receipt("1.5.3", False, "install")]) != []


def test_true_answers_are_left_alone() -> None:
    for answer in ("Estoy al día: tengo la 1.5.3 y la última publicada es la 1.5.2. No hay nada que actualizar.",
                   "No hay una versión más nueva.", "No estoy desactualizada.", "There's no newer version.",
                   "I'm not out of date.", "¿Quieres que busque si hay una versión más nueva?"):
        assert _found(answer, [_receipt("1.5.2", False)]) == [], answer


def test_never_beside_a_newer_version_nor_without_a_look() -> None:
    assert _found("Hay una versión más nueva disponible, la 1.5.4.", [_receipt("1.5.4", True)]) == []
    assert _found("Estoy desactualizado.", []) == []
