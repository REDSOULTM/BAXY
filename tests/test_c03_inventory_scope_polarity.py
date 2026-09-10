"""Page quantities and the polarity of an exhaustive-inventory claim."""
import copy

import pytest

from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect


def observation(count=2, total=7, complete=True, offset=0):
    return {
        "kind": "operation", "operation": "window.resolve", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {
            "windows": [{"title": f"Atlas {index}", "processName": "Viewer"} for index in range(count)],
            "count": count, "observedCount": total, "totalCount": total if complete else None,
            "offset": offset, "limit": 50, "complete": complete,
        },
    }


@pytest.mark.parametrize("pattern", [
    "Esta lista incluye {count} ventanas; hay más ventanas.",
    "La lista contiene {count} ventanas; el inventario es parcial.",
    "This list contains {count} windows; there are more windows.",
    "The list includes {count} windows; this is a partial inventory.",
])
@pytest.mark.parametrize("count,total", [(2, 7), (20, 25), (3, 8)])
def test_a_list_quantity_is_bound_to_the_page_not_the_selected_total(pattern, count, total):
    payload = _compose_situation_payload(observation(count, total), "en", "List the windows.")
    original = copy.deepcopy(payload)
    assert not _payload_fact_defect(pattern.format(count=count), payload)
    assert _payload_fact_defect(pattern.format(count=total), payload) == "reversed_result"
    assert payload == original


@pytest.mark.parametrize("pattern,negative", [
    ("La lista {neg}incluye todas las ventanas del inventario.", "no "),
    ("Esta página {neg}contiene todas las ventanas del inventario.", "no "),
    ("La lista {neg}muestra todas las ventanas del inventario.", "no "),
    ("Estas {neg}son todas las ventanas.", "no "),
    ("This list {neg}include all the windows in the inventory.", "does not "),
    ("This list {neg}show all the windows in the inventory.", "doesn't "),
    ("This page {neg}contain all the windows in the inventory.", "does not "),
    ("These are {neg}all of them.", "not "),
    ("La lista {neg}representa todas las ventanas del inventario.", "no "),
    ("Estas páginas {neg}representan todas las ventanas del inventario.", "no "),
    ("La lista {neg}abarca todas las ventanas del inventario.", "no "),
    ("This list {neg}represent all the windows in the inventory.", "does not "),
    ("These pages {neg}represent all the windows in the inventory.", "do not "),
    ("This list {neg}cover all the windows in the inventory.", "does not "),
])
@pytest.mark.parametrize("count,total,complete", [(2, 7, True), (3, 3, True), (2, 7, False), (2, 2, False)])
def test_exhaustiveness_is_bound_to_its_negation_and_known_page_scope(pattern, negative, count, total, complete):
    payload = _compose_situation_payload(observation(count, total, complete), "en", "List the windows.")
    positive = pattern.format(neg="")
    if positive.startswith("This "):
        positive = positive.replace(" include ", " includes ").replace(" show ", " shows ").replace(" contain ", " contains ")
    negated = pattern.format(neg=negative)
    if not complete and count == total:
        assert _payload_fact_defect(positive, payload) == "extra_claim"
        assert _payload_fact_defect(negated, payload) == "extra_claim"
    elif count == total:
        assert not _payload_fact_defect(positive, payload)
        assert _payload_fact_defect(negated, payload) == "reversed_result"
    else:
        assert _payload_fact_defect(positive, payload) == "extra_claim"
        assert not _payload_fact_defect(negated, payload)


@pytest.mark.parametrize("reply", [
    "Todas las ventanas mostradas en esta página son Atlas 0 y Atlas 1.",
    "All the windows listed on this page are Atlas 0 and Atlas 1.",
    "La página no incluye todas las ventanas del inventario.",
    "This page doesn't include all the windows in the inventory.",
    "No sé si son todas las ventanas; esta página muestra Atlas 0 y Atlas 1.",
    "I cannot confirm these are all the windows; this page shows Atlas 0 and Atlas 1.",
])
def test_local_quantifiers_and_unknown_exhaustiveness_are_not_global_claims(reply):
    payload = _compose_situation_payload(observation(), "en", "List the windows.")
    assert not _payload_fact_defect(reply, payload)


@pytest.mark.parametrize("reply", [
    "Esta página contiene todas las ventanas del inventario.",
    "This page includes all the windows in the inventory.",
    "La lista no incluye todas las ventanas; estas son todas las ventanas.",
    "This list does not include all the windows; these are all of them.",
    "No hay más ventanas.", "There are no other windows.",
])
def test_page_subject_or_another_negation_does_not_authorize_false_exhaustiveness(reply):
    payload = _compose_situation_payload(observation(), "en", "List the windows.")
    assert _payload_fact_defect(reply, payload) == "extra_claim"


@pytest.mark.parametrize("name", ["All windows", "Todas las ventanas", "No other windows", "Lista 20 ventanas"])
def test_observed_names_do_not_create_page_or_exhaustiveness_claims(name):
    source = observation(1, 7)
    source["observed"]["windows"][0]["title"] = name
    payload = _compose_situation_payload(source, "en", "List the windows.")
    assert not _payload_fact_defect(f'This page shows "{name}".', payload)


class Recorder(LlmRuntime):
    def __init__(self, model, reply):
        self._gguf = model
        self.reply = reply
        self.calls = 0

    def _post(self, payload):
        self.calls += 1
        return {"choices": [{"message": {"content": self.reply}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("model", ["Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "K2-Horizon-3.7B-Q4_K_M.gguf"])
@pytest.mark.parametrize("user_text,reply", [
    ("Lista las ventanas.", "Esta lista incluye 2 ventanas: Atlas 0 y Atlas 1. Hay más ventanas por listar."),
    ("List the windows.", "This list includes 2 windows: Atlas 0 and Atlas 1. There are more windows to list."),
    ("Lista las ventanas.", "Esta página muestra Atlas 0 y Atlas 1. La lista no incluye todas las ventanas del inventario."),
    ("List the windows.", "This page shows Atlas 0 and Atlas 1. The list does not include all the windows in the inventory."),
])
def test_a_faithful_answer_reaches_the_user_without_an_unnecessary_retry(model, user_text, reply):
    client = Recorder(model, reply)
    assert client.compose_user_message(user_text, "status", {"situation": observation()}) == reply
    assert client.calls == 1


@pytest.mark.parametrize("pattern", [
    "Se observaron {total} ventanas. Esta lista incluye {count} ventanas.",
    "Esta lista incluye {count} ventanas. Se observaron {total} ventanas.",
    "Se observaron {total} ventanas; esta lista incluye {count} de ellas.",
    "Observed: {total} windows. This list includes {count} of them.",
    "This list includes {count} windows. {total} windows were observed.",
    "Aquí tienes la lista:\n\n- Atlas 0\n\nSe observaron {total} ventanas. Esta página muestra {count} ventanas.",
    "Here is the list:\n\n- Atlas 0\n\nObserved: {total} windows. This page includes {count} of them.",
])
@pytest.mark.parametrize("count,total", [(1, 4), (3, 9), (20, 25)])
@pytest.mark.parametrize("complete", [True, False])
def test_two_bound_quantities_disclose_a_subset_without_a_required_phrase(pattern, count, total, complete):
    # This checks quantity interpretation, not whether all identities are listed.
    payload = _compose_situation_payload(observation(count, total, complete), "en", "List the windows.")
    before = copy.deepcopy(payload)
    assert not _payload_fact_defect(pattern.format(count=count, total=total), payload)
    assert _payload_fact_defect(pattern.format(count=count + 1, total=total), payload) == "reversed_result"
    assert _payload_fact_defect(pattern.format(count=count, total=total + 1), payload) == "reversed_result"
    assert payload == before


@pytest.mark.parametrize("pattern", [
    "This page shows {count} of the {total} visible windows observed.",
    "Esta página muestra {count} de las {total} ventanas observadas.",
    "The list includes {count} of {total} observed windows.",
])
@pytest.mark.parametrize("count,total", [(1, 4), (3, 9), (20, 25)])
@pytest.mark.parametrize("complete", [True, False])
def test_a_fraction_can_refer_to_observed_windows_without_asserting_global_total(pattern, count, total, complete):
    payload = _compose_situation_payload(observation(count, total, complete), "en", "List the windows.")
    assert not _payload_fact_defect(pattern.format(count=count, total=total), payload)
    assert _payload_fact_defect(pattern.format(count=count + 1, total=total), payload) == "reversed_result"
    assert _payload_fact_defect(pattern.format(count=count, total=total + 1), payload) == "reversed_result"


@pytest.mark.parametrize("reply", [
    "This page shows 2 of 7 windows.",
    "Esta lista muestra 2 de las 7 ventanas.",
    "The total is 7 windows. This page shows 2 windows.",
    "El total es 7 ventanas. Esta lista muestra 2 ventanas.",
])
def test_observed_denominators_do_not_authorize_unqualified_unknown_totals(reply):
    payload = _compose_situation_payload(observation(2, 7, False), "en", "List the windows.")
    assert _payload_fact_defect(reply, payload) == "extra_claim"


@pytest.mark.parametrize("reply", [
    "This list includes 2 windows.", "Esta lista incluye 2 ventanas.",
    "This list includes 2 of them.", "Esta lista incluye 2 de ellas.",
])
def test_page_quantity_alone_still_does_not_disclose_the_larger_inventory(reply):
    payload = _compose_situation_payload(observation(), "en", "List the windows.")
    assert _payload_fact_defect(reply, payload) == "missing_fact"


@pytest.mark.parametrize("pattern", [
    "Tienes abiertas {count} ventanas: {names}. Se observaron {total} ventanas.",
    "{count} ventanas abiertas: {names}. Se observaron {total} ventanas.",
    "You have {count} open windows: {names}. {total} windows were observed.",
    "{count} open windows: {names}. {total} windows were observed.",
])
@pytest.mark.parametrize("count,total", [(2, 7), (3, 8), (5, 11)])
@pytest.mark.parametrize("complete", [True, False])
def test_a_quantity_introducing_observed_names_counts_the_page(pattern, count, total, complete):
    source = observation(count, total, complete)
    names = ', '.join('"' + window['title'] + '"' for window in source['observed']['windows'])
    payload = _compose_situation_payload(source, 'en', 'List the windows.')
    reply = pattern.format(count=count, total=total, names=names)
    assert not _payload_fact_defect(reply, payload, 'List the windows.')
    bad = pattern.format(count=count + 1, total=total, names=names)
    assert _payload_fact_defect(bad, payload, 'List the windows.') == 'reversed_result'


@pytest.mark.parametrize("reply", [
    'Hay dos ventanas en total: "Atlas 0", "Atlas 1". Se observaron siete ventanas.',
    'In total there are two windows: "Atlas 0", "Atlas 1". Seven windows were observed.',
    'Hay dos ventanas. Esta página muestra "Atlas 0", "Atlas 1"; se observaron siete ventanas.',
    'There are two windows. This page shows "Atlas 0", "Atlas 1"; seven windows were observed.',
    'Hay dos ventanas: no puedo identificarlas. Esta página muestra "Atlas 0", "Atlas 1"; se observaron siete ventanas.',
    'There are two windows: I cannot identify them. This page shows "Atlas 0", "Atlas 1"; seven windows were observed.',
])
def test_a_later_list_does_not_relabel_an_explicit_or_unbound_global_count(reply):
    payload = _compose_situation_payload(observation(), 'en', 'List the windows.')
    assert _payload_fact_defect(reply, payload, 'List the windows.') == 'reversed_result'


@pytest.mark.parametrize("lead", ['', 'Currently, ', 'Right now, '])
@pytest.mark.parametrize("reply", [
    'There are no open windows currently visible.',
    'No open windows are currently visible.',
    'No open windows are visible in the current observation.',
])
@pytest.mark.parametrize("request_text", ['List all open windows.', 'List my windows.'])
def test_verified_empty_inventory_is_factual_prose_not_a_copied_instruction(lead, reply, request_text):
    answer = lead + reply
    client = Recorder('Qwen3-4B-Instruct-2507-Q4_K_M.gguf', answer)
    assert client.compose_user_message(request_text, 'status', {'situation': observation(0, 0)}) == answer
    assert client.calls == 1
    payload = _compose_situation_payload(observation(2, 2), 'en', request_text)
    assert _payload_fact_defect(answer, payload, request_text)
