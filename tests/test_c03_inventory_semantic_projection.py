"""Inventory page meaning, complete identities and unobserved chronology."""
import copy
import json

import pytest

from baxy_mind.llm import _compose_situation_payload, _payload_fact_defect, LlmRuntime
from baxy_mind.window_prose_facts import window_fact_feedback


def observation(count=2, total=7, offset=0, complete=True):
    return {
        "kind": "operation", "operation": "window.resolve", "polarity": "success",
        "verified": True, "succeeded": True,
        "observed": {
            "windows": [
                {"title": f"Órbita {index % 3}", "processName": f"Viewer{index % 2}",
                 "windowId": f"private_{index}", "foreground": index == 0,
                 "x": -index, "y": index * 5, "width": 321, "height": 456, "state": "normal"}
                for index in range(count)
            ],
            "count": count, "observedCount": total, "offset": offset, "limit": 50,
            "complete": complete, "totalCount": total if complete else None,
            "hasMore": offset + count < total,
            "nextOffset": offset + count if offset + count < total else None,
            "observationScope": "visible_top_level_windows",
            "pageConsistency": "fresh_enumeration_per_request",
        },
    }


@pytest.mark.parametrize("user_text", [
    "Lista las ventanas.", "Dime qué ventanas tengo abiertas.",
    "Muéstrame todas las ventanas abiertas.", "Show all open windows.",
    "What are the titles of my open windows?", "Which windows are open?",
    "Lista mis windows.", "Which ventanas tengo abiertas?",
    "Cuenta mis ventanas, please.", "How many windows are visible right now?",
])
@pytest.mark.parametrize("count", [1, 20, 50])
def test_identity_requests_keep_every_entry_and_its_multiplicity(user_text, count):
    situation = observation(count, count + 4)
    original = copy.deepcopy(situation)
    payload = _compose_situation_payload(situation, "es", user_text)
    assert payload["seen"]["windows"] == [
        {"title": window["title"], "processName": window["processName"]}
        for window in original["observed"]["windows"]
    ]
    assert payload["seen"]["count"] == count
    assert payload["seen"]["totalCount"] == count + 4
    assert situation == original


@pytest.mark.parametrize("user_text", [
    "¿Dónde están las ventanas?", "Dime las coordenadas de las ventanas.",
    "Lista las ventanas con sus tamaños.", "Which windows are maximized?",
    "Show all window positions and sizes.", "List the windows and tell me which has focus.",
    "Muestra las ventanas de Viewer1.", "List windows titled Órbita 1.",
    "Which window has focus?", "",
])
def test_unclassified_or_detailed_requests_keep_the_observed_details(user_text):
    situation = observation()
    projected = _compose_situation_payload(situation, "en", user_text)["seen"]["windows"]
    assert len(projected) == 2
    for index, window in enumerate(projected):
        assert window["x"] == -index
        assert window["y"] == index * 5
        assert window["width"] == 321
        assert window["height"] == 456
        assert window["state"] == "normal"
        assert window["is_current_window_for_user_interaction"] is (index == 0)


@pytest.mark.parametrize("count,total,offset,complete,entire", [
    (0, 0, 0, True, True), (2, 2, 0, True, True),
    (2, 7, 0, True, False), (2, 7, 2, True, False), (0, 7, 7, True, False),
    (2, 2, 0, False, None), (0, 0, 0, False, None),
    (2, 7, 0, False, False), (1, 7, 5, False, False),
])
def test_derived_scope_preserves_unknown_total_and_the_canonical_counts(count, total, offset, complete, entire):
    situation = observation(count, total, offset, complete)
    payload = _compose_situation_payload(situation, "en", "List the windows.")
    seen = payload["seen"]
    scope = seen["returnedPageScope"]
    assert scope == {
        "windowsListedOnThisPage": count,
        "totalWindowsInSelectedInventory": total if complete else None,
        "thisListIncludesEveryWindowInSelectedInventory": entire,
        "windowOpeningTimesObserved": False,
    }
    assert {key: value for key, value in seen.items() if key not in {"windows", "returnedPageScope"}} == {
        key: value for key, value in situation["observed"].items() if key != "windows"
    }


@pytest.mark.parametrize("mutation", [
    {"count": True}, {"count": 3}, {"observedCount": 1}, {"offset": -1},
    {"complete": "yes"}, {"totalCount": 8}, {"complete": False, "totalCount": 7},
])
def test_invalid_inventory_cannot_gain_derived_authority(mutation):
    situation = observation()
    situation["observed"].update(mutation)
    payload = _compose_situation_payload(situation, "en", "List the windows.")
    assert "returnedPageScope" not in payload["seen"]
    assert payload["seen"]["windows"][0]["width"] == 321


@pytest.mark.parametrize("flag", ["verified", "succeeded"])
@pytest.mark.parametrize("value", [False, None, "true", 1])
def test_only_verified_success_gets_semantic_projection(flag, value):
    situation = observation()
    situation[flag] = value
    assert "returnedPageScope" not in _compose_situation_payload(situation, "en", "List the windows.")["seen"]


@pytest.mark.parametrize("claim", [
    "Esta página incluye las dos más recientes.",
    "Esta página muestra las ventanas más antiguas.",
    "Esta página enumera las más nuevas.",
    "Esta página muestra las últimas abiertas.",
    "En esta página están las primeras en abrirse.",
    "Esta página tiene orden cronológico.",
    "Esta página está ordenada por fecha.",
    "This page lists the two most recent windows.",
    "This page contains the newest windows.",
    "This page shows the oldest windows.",
    "These are the latest windows on this page.",
    "The windows in this page are ordered by opening time.",
    "This page lists the last opened windows.",
    "This page contains the recently opened windows.",
    "Esta página muestra las most recent windows.",
])
@pytest.mark.parametrize("count,total", [(2, 7), (3, 3)])
def test_inventory_cannot_establish_opening_times_or_chronology(claim, count, total):
    payload = _compose_situation_payload(observation(count, total), "en", "List the windows.")
    assert _payload_fact_defect(claim, payload, "List the windows.") == "extra_claim"
    assert window_fact_feedback(claim, payload) == {
        "unsupported_claim": {"predicate": "window_opening_chronology", "observed": False},
        "rejected_draft": claim,
    }


@pytest.mark.parametrize("reply", [
    "Esta página muestra dos ventanas. No sé cuáles son las más recientes.",
    "Esta página muestra dos ventanas. No puedo determinar su orden cronológico.",
    "This page lists two windows. I cannot tell which are the newest.",
    "This page lists two windows. Their opening order is unknown.",
    "Esta página muestra dos ventanas; el orden cronológico no está comprobado.",
    "This page lists two windows. These are the first two entries of the inventory.",
    "Esta página contiene las primeras dos entradas del inventario.",
])
def test_unknown_chronology_and_page_positions_are_not_recency_claims(reply):
    payload = _compose_situation_payload(observation(), "en", "List the windows.")
    assert not _payload_fact_defect(reply, payload, "List the windows.")
    assert window_fact_feedback(reply, payload) is None


@pytest.mark.parametrize("name", ["Latest", "Newest", "Más recientes", "Chronological", "Últimas abiertas"])
def test_chronology_words_in_observed_identities_remain_opaque(name):
    situation = observation(1, 1)
    situation["observed"]["windows"][0]["title"] = name
    payload = _compose_situation_payload(situation, "en", "List the windows.")
    assert not _payload_fact_defect(f'This page contains "{name}".', payload)
    assert not _payload_fact_defect(f"This page contains one window:\n- {name}", payload)
    assert _payload_fact_defect(f'This page contains "{name}". It is the newest window.', payload) == "extra_claim"


class Capture(LlmRuntime):
    def __init__(self, model):
        self._gguf = model
        self.requests = []
        self.replies = iter([
            "This page lists the two newest windows: Órbita 0 and Órbita 1.",
            "This page lists two of seven windows: Órbita 0 and Órbita 1.",
        ])

    def _post(self, payload):
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("model", ["Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "K2-Horizon-3.7B-Q4_K_M.gguf"])
def test_compositor_applies_the_same_factual_rule_to_both_model_families(model):
    client = Capture(model)
    reply = client.compose_user_message("List the windows.", "status", {"situation": observation()})
    assert reply == "This page lists two of seven windows: Órbita 0 and Órbita 1."
    assert len(client.requests) == 2
    assert '"windowOpeningTimesObserved": false' in client.requests[0]["messages"][1]["content"]


@pytest.mark.parametrize("model", ["Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "K2-Horizon-3.7B-Q4_K_M.gguf"])
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("count,total", [(2, 7), (20, 25), (3, 3)])
@pytest.mark.parametrize("attempts", [2, 3])
def test_inventory_repair_preserves_every_entry_and_corrects_the_current_draft(model, language, count, total, attempts):
    situation = observation(count, total)
    original = copy.deepcopy(situation)
    names = "\n".join('- "' + w["title"] + '"' for w in situation["observed"]["windows"])
    request = "Lista las ventanas." if language == "es" else "List the windows."
    prefix = (f"Esta página muestra {count} de {total} ventanas" if language == "es"
              else f"This page lists {count} of {total} windows")
    wrong = [prefix + suffix + ":\n" + names for suffix in (
        [", las más recientes", ", las más antiguas"] if language == "es" else [", the newest", ", the oldest"])]
    good = prefix + ":\n" + names
    client = Capture(model)
    client.replies = iter(wrong[:attempts - 1] + [good])
    assert client.compose_user_message(request, "status", {"situation": situation}) == good
    assert len(client.requests) == attempts
    first_user = client.requests[0]["messages"][1]["content"]
    assert "Verified factual correction" not in first_user
    for index, payload in enumerate(client.requests[1:]):
        system = payload["messages"][0]["content"]
        user, feedback = payload["messages"][1]["content"].split("\nVerified factual correction: ")
        first_request, first_facts = first_user.split("\nsituation: ", 1)
        retry_request, retry_facts = user.split("\nsituation: ", 1)
        assert retry_request == first_request
        assert json.JSONDecoder().raw_decode(retry_facts)[0] == json.JSONDecoder().raw_decode(first_facts)[0]
        assert json.loads(feedback) == {
            "unsupported_claim": {"predicate": "window_opening_chronology", "observed": False},
            "rejected_draft": wrong[index],
        }
        assert "One sentence" not in system and "One short sentence" not in system
        assert payload["max_tokens"] == client.requests[0]["max_tokens"]
    assert situation == original


def test_nested_results_keep_their_own_page_scope_without_mutating_the_snapshot():
    first, second = observation(), observation(1, 1)
    situation = {"steps": [first, second]}
    original = copy.deepcopy(situation)
    payload = _compose_situation_payload(situation, "en", "List the windows.")
    scopes = [step["resultAtThisStep"]["seen"]["returnedPageScope"] for step in payload["completedStepsInOrder"]]
    assert [scope["thisListIncludesEveryWindowInSelectedInventory"] for scope in scopes] == [False, True]
    assert situation == original


@pytest.mark.parametrize("reply", [
    "This page is the latest observation of the windows.",
    "This page is the most recent snapshot of the windows.",
    "Esta página muestra la lectura más reciente de las ventanas.",
    "Esta página contiene la observación más reciente de las ventanas.",
])
def test_fresh_observation_does_not_assert_recent_window_opening(reply):
    payload = _compose_situation_payload(observation(), "en", "List the windows.")
    assert not _payload_fact_defect(reply, payload)


@pytest.mark.parametrize("reply", [
    "This page is the latest observation and contains the newest windows.",
    "Esta página muestra la lectura más reciente y las ventanas más antiguas.",
    "This page lists the newest windows; their owner is unknown.",
    "An unknown owner has the newest windows in this page.",
    "I cannot tell their size, but this page lists the most recent windows.",
    "Esta página muestra las ventanas más recientes; su tamaño no está comprobado.",
])
def test_uncertainty_or_freshness_about_another_fact_does_not_authorize_recency(reply):
    payload = _compose_situation_payload(observation(), "en", "List the windows.")
    assert _payload_fact_defect(reply, payload) == "extra_claim"
