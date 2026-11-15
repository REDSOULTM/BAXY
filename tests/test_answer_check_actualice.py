"""Rule «update_early», INT36F («Baxi, actualízate» on int36c: «Ya te actualicé a la versión 1.5.4.» 1 of 20 right after
baxy_update install, whose receipt says the installer only started; BAXY is replaced after the turn and the new one says
«Me actualicé» by itself). A claim that BAXY is updated, said in a turn whose baxy.update shows a newer version not yet
installed («updated» false, or «newer» true from a check), is a state no receipt backs: the fact goes back to the
model, as «mostré» does. Same family as ACT1's «unchecked_update»; the claim is read in Spanish and English."""
import json

from baxy_mind.answer_check import check

FACTS = {"version": 1, "channel": "github", "installed": "1.5.3", "checked": True, "latest": "1.5.4"}
INSTALLED = {"op": "baxy.update", "tool": "baxy_update", "arguments": {"action": "install"}, "observation": json.dumps(
    {"status": "completed", "verification": "delivered_only", "observed": {
        **FACTS, "installerStarted": True, "installerBytes": 81354404, "updated": False, "delivered": True}}),
    "outcome": "completado", "completed": True, "read": False}
CHECKED = {"op": "baxy.update", "tool": "baxy_update", "arguments": {"action": "check"}, "observation": json.dumps(
    {"status": "completed", "verification": "readback", "observed": {**FACTS, "newer": True,
                                                                     "downloadBytes": 81354404}}),
    "outcome": "completado y verificado", "completed": True, "read": True}
LATEST = {"op": "baxy.update", "tool": "baxy_update", "arguments": {"action": "check"}, "observation": json.dumps(
    {"status": "completed", "verification": "readback", "observed": {**FACTS, "latest": "1.5.3", "newer": False}}),
    "outcome": "completado y verificado", "completed": True, "read": True}


def _found(answer: str, receipts: list[dict], request: str = "Baxi, actualízate") -> list[dict]:
    session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return [f for f in check(answer, request, receipts, session) if f["rule"] in ("update_early", "update_not_installed")]


def test_updated_said_right_after_the_installer_started_is_found() -> None:
    for answer in ("Ya te actualicé a la versión 1.5.4.", "¡Listo! Me actualicé a la 1.5.4.",
                   "Ya estoy actualizada a la versión 1.5.4.", "He actualizado BAXY a la versión 1.5.4.",
                   "Ya tienes la versión 1.5.4.", "La actualización está lista.",
                   "Estoy actualizándome ahora, la versión 1.5.4 ya está instalada y BAXY se reiniciará en breve."):
        found = _found(answer, [CHECKED, INSTALLED])
        assert [f["rule"] for f in found] == ["update_early"], answer
        assert "1.5.4" in found[0]["fact"] and "todavía no" in found[0]["fact"], answer


def test_updated_said_after_only_a_check_is_found() -> None:
    found = _found("Ya te actualicé a la versión 1.5.4.", [CHECKED])
    assert [f["rule"] for f in found] == ["update_not_installed"]
    assert "no se instaló nada" in found[0]["fact"]
    # Held-out 1: told as under way or about to start with no install called.
    for answer in ("I'm updating you to the latest version now.", "¡Ya hay versión 1.5.4 disponible! Voy a instalarla ahora.",
                   "Me estoy actualizando a la 1.5.4."):
        assert [f["rule"] for f in _found(answer, [CHECKED])] == ["update_not_installed"], answer
    # Under way is true once the installer started.
    assert _found("Me estoy actualizando a la 1.5.4: me cierro y vuelvo sola.", [CHECKED, INSTALLED]) == []


def test_a_question_after_only_a_check_with_a_newer_version_gets_the_fact_once() -> None:
    # «Baxi, update yourself» in English: «There is a newer version of BAXY available. Would you like me to update
    # now?» 20 of 20 after the check alone. Whether they asked to update or only whether there is one, the model reads.
    for answer, request in (("There is a newer version of BAXY available. Would you like me to update now?",
                             "Baxi, update yourself"),
                            ("Sí, hay una versión más nueva: 1.5.4. ¿Quieres que te la instale?",
                             "¿hay una versión nueva tuya?")):
        found = [f for f in check(answer, request, [CHECKED], [("baxy.update", True, True)])
                 if f["rule"] == "update_offered"]
        assert len(found) == 1, answer
        assert "install" in found[0]["fact"] and "1.5.4" in found[0]["fact"], answer
    # Not after the install, nor with nothing newer, nor in an answer with no question.
    for answer, receipts in (("Me estoy actualizando. ¿Quieres algo más?", [CHECKED, INSTALLED]),
                             ("Estás al día. ¿Algo más?", [LATEST]),
                             ("Hay una versión nueva, la 1.5.4.", [CHECKED])):
        session = [(r["op"], r["completed"], r["read"]) for r in receipts]
        assert not [f for f in check(answer, "Baxi, actualízate", receipts, session)
                    if f["rule"] == "update_offered"], answer


def test_in_english_too() -> None:
    for answer in ("I've updated to version 1.5.4.", "Done, I updated myself to 1.5.4.", "You're now on 1.5.4.",
                   "Version 1.5.4 is installed and I'll restart shortly."):
        assert [f["rule"] for f in _found(answer, [INSTALLED], "Baxy, update yourself")] == ["update_early"], answer


def test_what_is_true_is_not_found() -> None:
    for answer in ("Me estoy actualizando a la versión 1.5.4: me cerraré y volveré a abrirme sola.",
                   "Estoy bajando la versión 1.5.4; todavía no estoy actualizada.",
                   "¿Quieres que la actualice ahora?", "Hay una versión nueva, la 1.5.4. ¿Te la instalo?",
                   "I'm updating to 1.5.4 now; I'll close and open again by myself."):
        assert _found(answer, [CHECKED, INSTALLED]) == [], answer
    # Up to date is true when the check says nothing newer.
    assert _found("Ya estoy actualizada: tienes la última versión, la 1.5.3.", [LATEST], "¿estás al día?") == []
    # With no baxy.update in the turn this rule reads nothing (ACT1 and the acts read the rest).
    assert _found("Ya actualicé la nota.", []) == []
