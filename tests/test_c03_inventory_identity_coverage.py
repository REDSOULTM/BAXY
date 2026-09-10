"""An inventory answer conserves identities and exact repeated-entry counts."""
import copy

import pytest

from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect
from baxy_mind.window_prose_facts import window_fact_feedback


def observation(names, repeat):
    windows = [{"title": name, "processName": f"Viewer{index}"}
               for name in names for index in range(repeat)]
    return {"kind": "operation", "operation": "window.resolve", "verified": True,
            "succeeded": True, "polarity": "success", "observed": {
                "windows": windows, "count": len(windows), "observedCount": len(windows),
                "totalCount": len(windows), "offset": 0, "complete": True,
            }}


NAMES = [("Atlas", "Atlas 2"), ("Informe.2026", "Música (mezcla)"), ("Órbita 17", "Review 3")]
REQUESTS = ["Lista las ventanas.", "Dime qué ventanas tengo abiertas.", "List all open windows.", "Lista mis windows."]


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("repeat", [1, 2, 4])
@pytest.mark.parametrize("request_text", REQUESTS)
def test_each_observed_entry_or_its_explicit_count_is_required(names, repeat, request_text):
    payload = _compose_situation_payload(observation(names, repeat), "es", request_text)
    good = "\n".join('- "' + name + '"' for name in names for _ in range(repeat))
    bad = "\n".join(good.splitlines()[:-1])
    assert not _payload_fact_defect(good, payload, request_text)
    assert _payload_fact_defect(bad, payload, request_text) == "missing_fact"
    feedback = window_fact_feedback(bad, payload, request_text)
    assert feedback["missing_answer"]["predicate"] == "window_inventory_identity_counts"
    assert feedback["rejected_draft"] == bad


@pytest.mark.parametrize("pattern", [
    '"{name}" ({count} ventanas)', '"{name}" ({count} windows)',
    '"{name}": {count} instancias', '"{name}" — {count} instances',
    '"{name}" × {count}', '"{name}" x{count}',
    '{count} ventanas de "{name}"', '{count} windows of "{name}"',
    '{count} "{name}" windows', '{count} × "{name}"',
])
@pytest.mark.parametrize("count", [2, 4, 7])
def test_group_counts_belong_to_the_named_identity_not_the_whole_inventory(pattern, count):
    names = ["Atlas", "Atlas 2", "Review.1"]
    payload = _compose_situation_payload(observation(names, count), "en", "List the windows.")
    good = "; ".join(pattern.format(name=name, count=count) for name in names)
    bad = good.replace(pattern.format(name=names[-1], count=count), pattern.format(name=names[-1], count=count + 1))
    assert not _payload_fact_defect(good, payload, "List the windows.")
    assert _payload_fact_defect(bad, payload, "List the windows.") == "reversed_result"


@pytest.mark.parametrize("reply", [
    '"Atlas", "Review": cuatro ventanas de cada título.',
    '"Atlas", "Review": four windows each.',
    '"Atlas" y "Review" (cuatro ventanas cada una).',
    '"Atlas" and "Review" (four windows each).',
])
def test_an_explicit_shared_count_covers_every_named_identity(reply):
    payload = _compose_situation_payload(observation(["Atlas", "Review"], 4), "en", "List the windows.")
    assert not _payload_fact_defect(reply, payload, "List the windows.")
    assert _payload_fact_defect(reply.replace('four', 'five').replace('cuatro', 'cinco'), payload, "List the windows.") == "reversed_result"


@pytest.mark.parametrize("tail", [
    "Algunas se repiten.", "Several occur more than once.", "Hay ocho ventanas en total.",
    "There are eight windows in total.", "Hay cuatro procesos.", "PID4 y PID7.",
])
def test_vague_repetitions_or_global_numbers_cannot_replace_per_identity_counts(tail):
    payload = _compose_situation_payload(observation(["Atlas", "Review"], 4), "en", "List the windows.")
    assert _payload_fact_defect('"Atlas", "Review". ' + tail, payload, "List the windows.") == "missing_fact"


@pytest.mark.parametrize("request_text", ["How many windows are open?", "¿Cuántas ventanas tengo abiertas?", "Cuenta mis ventanas."])
def test_a_count_only_request_does_not_require_all_titles(request_text):
    payload = _compose_situation_payload(observation(["Atlas", "Review"], 4), "en", request_text)
    assert not _payload_fact_defect('Hay ocho ventanas en total.', payload, request_text)
    assert window_fact_feedback('Hay ocho ventanas en total.', payload, request_text) is None


@pytest.mark.parametrize("title", ["", "   "])
def test_process_identity_is_only_a_fallback_for_an_empty_title(title):
    source = observation(["Atlas", title], 1)
    source['observed']['windows'][1]['processName'] = 'Companion'
    payload = _compose_situation_payload(source, "en", "List the windows.")
    assert not _payload_fact_defect('"Atlas", "Companion".', payload, "List the windows.")
    assert _payload_fact_defect('"Viewer0", "Companion".', payload, "List the windows.") == "missing_fact"


@pytest.mark.parametrize("request_text", ["List the windows.", "How many windows are open?", ""])
def test_explicit_excessive_group_count_is_false_even_without_a_list_request(request_text):
    payload = _compose_situation_payload(observation(["Atlas", "Review"], 4), "en", request_text)
    assert _payload_fact_defect('Atlas (five windows); Review (four windows).', payload, request_text) == "reversed_result"


@pytest.mark.parametrize("reply", [
    'Atlas (three windows). Atlas is visible. Review (four windows).',
    'Atlas is visible. Atlas is maximized. Atlas has a title. Atlas is open. Review (four windows).',
])
def test_descriptive_references_do_not_supply_missing_instances(reply):
    payload = _compose_situation_payload(observation(["Atlas", "Review"], 4), "en", "List the windows.")
    assert _payload_fact_defect(reply, payload, "List the windows.") == "missing_fact"


def test_a_group_and_a_separate_entry_can_jointly_cover_a_title():
    payload = _compose_situation_payload(observation(["Atlas", "Review"], 4), "en", "List the windows.")
    assert not _payload_fact_defect('Atlas (three windows); Atlas; Review (four windows).', payload, "List the windows.")


@pytest.mark.parametrize("names", NAMES)
@pytest.mark.parametrize("repeat", [2, 4])
@pytest.mark.parametrize("ending", [".", "!", "?"])
@pytest.mark.parametrize("tail", ["Algunas ventanas se repiten.", "Some windows occur more than once."])
def test_sentence_after_the_final_title_does_not_erase_its_one_mention(names, repeat, ending, tail):
    source = observation(names, repeat)
    reply = ', '.join('"' + name + '"' for name in names) + ending + ' ' + tail
    payload = _compose_situation_payload(source, 'en', 'List the windows.')
    feedback = window_fact_feedback(reply, payload, 'List the windows.')
    missing = feedback['missing_answer']['identities']
    assert len(missing) == len(names)
    assert {item['identified_in_draft'] for item in missing.values()} == {1}
    assert {item['observed'] for item in missing.values()} == {repeat}
    assert _payload_fact_defect(reply, payload, 'List the windows.') == 'missing_fact'


@pytest.mark.parametrize("process", ['Companion', 'Reader.2026', 'Agent (helper)'])
@pytest.mark.parametrize("title", ['', '   ', None])
@pytest.mark.parametrize("pattern", [
    'Atlas ({process})', 'Atlas (process: {process})',
    'Atlas (proceso: {process})', 'Atlas — ({process})',
])
def test_an_annotated_process_does_not_supply_an_independent_unnamed_window(process, title, pattern):
    source = observation(['Atlas', title], 1)
    for window in source['observed']['windows']:
        window['processName'] = process
    payload = _compose_situation_payload(source, 'en', 'List the windows.')
    incomplete = pattern.format(process=process) + '.'
    complete = pattern.format(process=process) + ', "' + process + '".'
    assert _payload_fact_defect(incomplete, payload, 'List the windows.') == 'missing_fact'
    assert not _payload_fact_defect(complete, payload, 'List the windows.')


class Recorder(LlmRuntime):
    def __init__(self, model):
        self._gguf = model
        self.requests = []
        self.replies = iter(['Atlas, Review. Algunas ventanas se repiten.', 'Atlas (cuatro ventanas); Review (cuatro ventanas).'])

    def _post(self, payload):
        self.requests.append(copy.deepcopy(payload))
        return {'choices': [{'message': {'content': next(self.replies)}, 'finish_reason': 'stop'}]}


@pytest.mark.parametrize("model", ['Qwen3-4B-Instruct-2507-Q4_K_M.gguf', 'K2-Horizon-3.7B-Q4_K_M.gguf'])
def test_existing_retry_gets_the_missing_facts_and_delivers_the_complete_grouping(model):
    client = Recorder(model)
    source = observation(['Atlas', 'Review'], 4)
    before = copy.deepcopy(source)
    assert client.compose_user_message('Lista las ventanas.', 'status', {'situation': source}) == 'Atlas (cuatro ventanas); Review (cuatro ventanas).'
    assert len(client.requests) == 2
    assert 'window_inventory_identity_counts' not in client.requests[0]['messages'][1]['content']
    assert 'window_inventory_identity_counts' in client.requests[1]['messages'][1]['content']
    assert client.requests[0]['max_tokens'] == client.requests[1]['max_tokens']
    assert source == before
