"""Record root whole-answer adjudication of completed, immutable diagnostic785."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'PROSE_SAMPLING785'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-prose-sampling785-private'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(text.encode('utf-8'))


cases = read(PRIVATE / 'cases.json')
results = read(PRIVATE / 'results.json')
planned = read(PRIVATE / 'planned.json')
prereg = read(OUT / 'PREREG.json')
run = read(OUT / 'RESULT.json')
assert len(cases) == 50 and len(results) == len(planned) == 150
assert sha(PRIVATE / 'cases.json') == prereg['cases_sha256']
assert sha(PRIVATE / 'planned.json') == prereg['planned_sha256']
assert sha(ROOT / 'scratchpad/c03-prose-sampling785.py') == prereg['driver_sha256']
assert all(sha(ROOT / p) == h for p, h in prereg['source_pins'].items())
assert run['driver_unchanged'] and run['sources_unchanged'] and not run['violations']

# Explicit human decisions, following full reading; not a model/regex/validator score.
# Order in each string is A/B/C. P means the complete answer is accredited.
decisions = {
    'H0023': 'FPP', 'H0103': 'FFF', 'H0539': 'FFF', 'H0655': 'FFF',
    'H0508': 'FFF', 'clock-variant779-31': 'FFF',
    'inventory785-1-1': 'PPP', 'inventory785-1-2': 'FFF',
    'inventory785-1-3': 'PPP', 'inventory785-1-4': 'PFP',
    'inventory785-2-1': 'PPP', 'inventory785-2-2': 'PFP',
    'inventory785-2-3': 'PPP', 'inventory785-2-4': 'PPP',
    'inventory785-3-1': 'PPP', 'inventory785-3-2': 'PPP',
    'inventory785-3-3': 'PPP', 'inventory785-3-4': 'PPP',
    'inventory785-4-1': 'PPP', 'inventory785-4-2': 'FPP',
    'inventory785-4-3': 'PPP', 'inventory785-4-4': 'PPP',
    'inventory785-5-1': 'FFF', 'inventory785-5-2': 'FFF',
    'inventory785-5-3': 'FFF', 'inventory785-5-4': 'FFF',
    'inventory785-6-1': 'FPF', 'inventory785-6-2': 'FFF',
    'inventory785-6-3': 'FFF', 'inventory785-6-4': 'FFF',
    'memory785-1-1': 'PPP', 'memory785-1-2': 'PPP',
    'memory785-1-3': 'PPP', 'memory785-1-4': 'PPP',
    'memory785-2-1': 'PPP', 'memory785-2-2': 'PPP',
    'memory785-2-3': 'PPP', 'memory785-2-4': 'PPP',
    'memory785-3-1': 'FFF', 'memory785-3-2': 'FPP',
    'memory785-3-3': 'PPP', 'memory785-3-4': 'PPP',
    'memory785-4-1': 'FFF', 'memory785-4-2': 'PPP',
    'memory785-4-3': 'PPP', 'memory785-4-4': 'PPP',
    'memory785-5-1': 'FFF', 'memory785-5-2': 'PPP',
    'memory785-5-3': 'PPP', 'memory785-5-4': 'PPP',
}
assert set(decisions) == {c['id'] for c in cases}
arms = ['A_registered_greedy', 'B_qwen_recommended_seed0', 'C_qwen_recommended_seed17']
lookup = {(r['case_id'], r['arm']): r for r in results}
assert len(lookup) == 150
plans = {(r['case_id'], r['arm']): r['payload'] for r in planned}
assert set(lookup) == set(plans)
notes = {}


def note(case_id, labels, tags, reason):
    for label in labels:
        notes[(case_id, label)] = {'defects': tags, 'reason': reason}


note('H0023', 'A', ['unsupported_chronology'], 'Conserva las 20 entradas y el total 25, pero inventa que las 20 son las más recientes; no hay tiempos de apertura.')
note('H0103', 'ABC', ['inventory_multiplicity'], 'Resume categorías con varias instancias sin sus cantidades; omite identidades observadas. El alcance 20/25 no sustituye una lista completa de la página.')
note('H0539', 'A', ['measurement_label', 'wrong_subject'], 'Llama disponible a 16,54 GB utilizables; los disponibles son aproximadamente 1,98 GB. Tengo también atribuye al narrador la RAM del PC.')
note('H0539', 'BC', ['measurement_label', 'wrong_subject'], 'Llama instalada a 16,54 GB utilizables; la instalada observada es 17,18 GB. Tengo cambia el sujeto.')
note('H0655', 'A', ['measurement_label', 'wrong_subject'], 'Disponible en total no distingue la capacidad utilizable de la memoria libre, que es aproximadamente 1,97 GB; además dice Tengo.')
note('H0655', 'BC', ['wrong_subject'], 'Las cifras posteriores distinguen libre, usada e instalada correctamente. Disponible en total es una etiqueta ambigua, no se declara que todas las cifras sean falsas. El sujeto Tengo sigue siendo incorrecto para el PC del usuario.')
note('H0508', 'ABC', ['measurement_label', 'wrong_subject'], 'La versión observada de Windows se conserva; llama disponible a 16,54 GB utilizables, frente a aproximadamente 1,97 GB disponibles. Tengo cambia el sujeto.')
note('clock-variant779-31', 'ABC', ['spelling'], 'La hora 16:34 es correcta, pero los tres brazos conservan Marka. No cumple el criterio de prosa de C03.')
note('inventory785-1-2', 'ABC', ['wrong_subject'], 'El inventario vacío es correcto, pero No tengo atribuye al narrador las ventanas por las que preguntó el usuario.')
note('inventory785-1-4', 'B', ['wrong_subject'], 'El inventario vacío es correcto, pero I do not have atribuye las ventanas al narrador.')
note('inventory785-2-2', 'B', ['wrong_subject'], 'Conserva títulos y página 2/7; Tengo atribuye las ventanas al narrador. Solo he podido ver dos es además una formulación ambigua de la página, no se cuenta como otra falsedad demostrada.')
note('inventory785-4-2', 'A', ['inventory_multiplicity'], 'Da cinco títulos y algunas se repiten, sin multiplicidades 3,3,2,2,2 de las doce entradas.')
for layout in [5, 6]:
    note(f'inventory785-{layout}-2', 'ABC', ['inventory_multiplicity'], 'Da cinco títulos sin las cuatro instancias de cada título. Varias/algunas no preserva las veinte entradas. No se interpreta observado como total conocido cuando complete es false.')
    for variant in [1, 3, 4]:
        labels = 'AC' if layout == 6 and variant == 1 else 'ABC'
        note(f'inventory785-{layout}-{variant}', labels, ['output_limit', 'inventory_multiplicity'], 'Termina por length a 256 tokens en medio de una identidad, sin completar las veinte entradas ni la declaración de alcance. Es un corte del presupuesto de la integración, no prueba de incapacidad nativa.')
for case_id in ['memory785-3-1', 'memory785-4-1']:
    note(case_id, 'ABC', ['wrong_subject'], 'Las cantidades son correctas. Tengo atribuye la capacidad del PC del usuario al narrador; se separa del eje numérico y se aplica el mismo criterio de sujeto que en CPU/batería.')
note('memory785-3-2', 'A', ['measurement_label'], 'Disponible cero es correcto, pero toda la memoria instalada confunde 32 GB instalados con 31,6 GB utilizables y usados.')
note('memory785-5-1', 'A', ['wrong_subject'], 'No afirma instalada: 12 GB es capacidad utilizable, con 3,5 libres y 8,5 usados. Disponible en total queda ambiguo; se rechaza por Tengo, sin inventar una afirmación de capacidad instalada.')
note('memory785-5-1', 'BC', ['measurement_label', 'wrong_subject'], 'Afirma 12 GB instalados aunque installedBytes es desconocido; 12 GB es la capacidad utilizable. Tengo también cambia el sujeto.')

rows, telemetry = [], []
for c in cases:
    first = plans[(c['id'], arms[0])]
    for index, arm in enumerate(arms):
        r = lookup[(c['id'], arm)]
        payload = plans[(c['id'], arm)]
        assert payload['messages'] == first['messages']
        assert payload['max_tokens'] == 256 and payload['cache_prompt'] is False
        assert payload['chat_template_kwargs'] == first['chat_template_kwargs']
        assert 'error' not in r
        choice = r['response']['choices'][0]
        answer = choice['message']['content']
        passed = decisions[c['id']][index] == 'P'
        detail = notes.get((c['id'], arm[0]))
        assert passed == (detail is None), (c['id'], arm)
        slot = max((s for s in r['slots_after'] if 'id_task' in s), key=lambda s: s['id_task'])
        params = slot['params']
        expected = ({'temperature': 0., 'top_k': 40, 'top_p': .95, 'min_p': .05, 'seed': 4294967295}
                    if index == 0 else {'temperature': .7, 'top_k': 20, 'top_p': .8, 'min_p': 0., 'seed': 0 if index == 1 else 17})
        expected.update(presence_penalty=0., repeat_penalty=1., n_predict=256, max_tokens=256)
        assert all(math.isclose(params[k], v, rel_tol=1e-6, abs_tol=1e-7) for k, v in expected.items())
        assert slot['n_ctx'] == 4096 and slot['n_prompt_tokens_cache'] == 0
        assert r['response']['usage']['prompt_tokens_details']['cached_tokens'] == 0
        rows.append({'case_id': c['id'], 'arm': arm, 'passed': passed,
                     'defects': [] if passed else detail['defects'],
                     'reason': 'Respuesta completa contrastada: petición, hechos, alcance, cantidades y sujeto conservados.' if passed else detail['reason'],
                     'finish_reason': choice['finish_reason'], 'seconds': r['seconds'],
                     'answer_sha256': hashlib.sha256(answer.encode('utf-8')).hexdigest()})
        telemetry.append({'case_id': c['id'], 'arm': arm, 'slot_id': slot['id'], 'id_task': slot['id_task'],
                          'n_ctx': slot['n_ctx'], 'n_prompt_tokens_cache': slot['n_prompt_tokens_cache'],
                          'effective_params': {k: params[k] for k in expected}, 'samplers': params['samplers'], 'matches': True})

metrics = {}
for arm in arms:
    selected = [r for r in rows if r['arm'] == arm]
    durations = sorted(r['seconds'] for r in selected)
    metrics[arm] = {'pass': sum(r['passed'] for r in selected), 'fail': sum(not r['passed'] for r in selected),
                    'finish_reason': dict(Counter(r['finish_reason'] for r in selected)),
                    'final_seconds_p50': statistics.median(durations),
                    'final_seconds_p95_nearest_rank': durations[math.ceil(.95 * len(durations)) - 1],
                    'final_seconds_max': max(durations),
                    'generation_tokens_per_second_p50': statistics.median(lookup[(c['id'], arm)]['response']['timings']['predicted_per_second'] for c in cases)}
pairs = {}
for index, arm in enumerate(arms[1:], 1):
    pairs[arm] = {kind: [c['id'] for c in cases if (decisions[c['id']][0], decisions[c['id']][index]) == values]
                  for kind, values in {'both_pass': ('P','P'), 'gain': ('F','P'), 'regression': ('P','F'), 'both_fail': ('F','F')}.items()}
assert [metrics[a]['pass'] for a in arms] == [30, 32, 33]
assert sum(r['finish_reason'] == 'length' for r in rows) == 17
adjudication = {'utc': datetime.now(timezone.utc).isoformat(), 'method': 'Root full-answer manual adjudication; explicit frozen decision matrix. No product validator, LLM judge or opening-sentence shortcut.',
    'review': 'Root read all150 responses, grouping only byte-identical whole strings within a case. RO inventory review confirmed24 inventory-content failures; root added5 independent subject failures, recorded separately.',
    'interpretations': ['Window identity may be given by title, or process when title is absent; unrequested process metadata is not mandatory. Multiplicity must remain explicit.',
        'Fresh observation wording is supported; most-recent windows is unsupported without opening times.',
        'First-person ownership of the user PC is a separate subject failure, not a quantity failure. This preserves the existing CPU/battery criterion.',
        'H0655 B/C and memory785-5-1 A have ambiguous available-total wording. Their correct component values are preserved and not re-labelled false; subject failure alone prevents whole-answer credit.',
        'Minor understandable agreement errors are not new failure categories. Repeated Marka remains the pre-existing clock blocker.'],
    'quality_adjudicated': True, 'metrics': metrics, 'paired_against_A': pairs, 'rows': rows,
    'adoption': False, 'survey_coverage_added': 0, 'scope': prereg['scope']}
write(OUT / 'ADJUDICATION.json', adjudication)
write(OUT / 'EFFECTIVE_PARAMS.json', {'selection_rule': 'For each sequential completed response choose slots_after entry with maximum id_task; global props defaults are not effective per-call parameters.',
    'float_tolerance': {'relative': 1e-6, 'absolute': 1e-7}, 'calls_verified': 150, 'deviations': [],
    'message_parity_cases': 50, 'same_256_budget_cases': 50, 'cache_prompt_false_calls': 150, 'rows': telemetry})


def response_markdown(selected):
    out = ['# Respuestas completas de 785\n', 'Diagnóstico de primer borrador con contexto BAXY; no comparación nativa de modelos. Puntuación de la respuesta completa.\n']
    for c in selected:
        out += [f"## {c['id']}\n", f"Petición literal: {c['request']}\n", f"Criterio congelado: {c['criterion']}\n",
                'Hechos suministrados:\n', '```json\n' + json.dumps(c['situation'], ensure_ascii=False, indent=2) + '\n```\n']
        for arm in arms:
            r = lookup[(c['id'], arm)]
            verdict = next(x for x in rows if x['case_id'] == c['id'] and x['arm'] == arm)
            out += [f"### {arm}: {'CUMPLE' if verdict['passed'] else 'FALLA'}\n", verdict['reason'] + '\n',
                    f"Final: {verdict['finish_reason']}; duración {r['seconds']:.3f} s.\n",
                    '```text\n' + r['response']['choices'][0]['message']['content'] + '\n```\n']
    return '\n'.join(out)


write(PRIVATE / 'RESPUESTAS.md', response_markdown(cases))
write(OUT / 'RESPUESTAS_SINTETICAS.md', response_markdown([c for c in cases if c['origin'].startswith('declared synthetic')]))
write(PRIVATE / 'ADJUDICATION.json', adjudication)
private_names = ['cases.json', 'planned.json', 'results.json', 'server-props.json', 'server.log', 'RESPUESTAS.md', 'ADJUDICATION.json']
write(OUT / 'PRIVATE_PINS.json', {'directory': str(PRIVATE), 'files': {name: sha(PRIVATE / name) for name in private_names}})
print(json.dumps({'metrics': metrics, 'pairs': {k: {name: len(ids) for name, ids in v.items()} for k, v in pairs.items()}, 'responses': len(rows)}, ensure_ascii=False))
