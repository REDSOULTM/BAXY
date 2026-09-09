"""Preserve all native comparisons, including failed controls and replay limits."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
names = ['guard-boundary594', 'guard-contract595', 'language-repair596',
         'language-wire597', 'language-backend598', 'language-template599',
         'history-request600', 'language-translation601']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


notes = {
    'guard-boundary594': 'La definición más precisa corrige H0012, pero conserva fallos de negación, tres argumentos incompletos y cuenta múltiple. No pasa el panel completo; no se adopta.',
    'guard-contract595': 'La segunda instrucción corrige H0012 y la negación, pero no los tres casos incompletos ni la cuenta múltiple. También emite one en siete conversaciones: derive_semantic_effect_state lo normaliza a zero, de modo que no es por sí solo regresión ejecutable. La rúbrica nativa exigía zero y se conserva. No se adopta ni se sigue variando ese prompt.',
    'language-repair596': 'El aviso de idioma no corrige las dos identidades y corta la explicación RAM. Esta reproducción tomó el input al constructor _post antes de unir el prefijo system; no equivale al envío efectivo del producto.597 corrige el instrumento;596 se conserva íntegro.',
    'language-wire597': 'Prefijo system unido exactamente como _post: las dos identidades originales siguen en español. La instrucción de reparación correcta produce razonamiento que consume96tokens y deja ambas respuestas cortadas. RAM mejora a inglés. No se adopta. Se verificaron saltos reales y ausencia de literales slash-n en el prefijo.',
    'language-backend598': 'Sólo backendb10865 frente a597: ambas identidades siguen fallando, con razonamiento y corte en el candidato. No corrige el síntoma ni se promueve. La explicación propuesta por el issue26781 fue refutada en su propia actualización; no atribuirle esta causa.',
    'language-template599': 'Sólo plantilla oficial2507 frente a597, mismob9980 y payloads: desaparecen cortes y reasoning_content en los12, pero ambas identidades candidatas vuelven a español. Mismo4/6 candidato; no se promueve como solución. Renders previamente iguales no implican idéntica capacidad del parser/gramática.',
    'history-request600': 'Agrupar sin pérdida historial y petición en un solo mensaje user no resuelve idioma:3/6 en ambos brazos; una identidad candidata se corta. No se adopta ni se elimina historial por este resultado.',
    'language-translation601': 'Traducir el borrador completo real, cuando sólo falla idioma, mejora3/6→6/6;12stop. Conserva BAXY, Sofia, Isabel, identidad española y hechos sobre RAM. Sigue siendo nativo: incorporar en el reintento existente sólo para conocimiento sin otro defecto, conservar guardas y probar producto. No se ha promovido fuente por estos seis aciertos.',
}
summaries = []
for name in names:
    out = base / ('astra-' + name)
    private = local / ('C03-' + name + '-private')
    assert not (out / 'RESULT.json').exists()
    resources = read(out / 'RESOURCES.json')
    assert resources['complete'] and not resources['violations'] and resources['manifest_unchanged']
    responses = rows(private / 'responses.jsonl')
    requests = rows(private / 'requests.jsonl')
    assert len(responses) == len(requests) == (32 if name.startswith('guard') else 12)
    adjudication = []
    counts = Counter()
    native_type_counts = Counter()
    for row in responses:
        choice = row['response']['choices'][0]
        wire = choice['message']['content']
        answer = json.loads(wire) if choice['finish_reason'] == 'stop' else None
        if name.startswith('guard'):
            expected_count = 'zero' if row['expected'] == 'stable_conversation' else 'multiple' if row['case_id'] == 'multiple-effects' else 'one'
            type_ok = isinstance(answer, dict) and answer.get('request_type') == row['expected']
            native_type_counts[row['arm']] += bool(type_ok)
            correct = type_ok and answer.get('effect_count') == expected_count
            reason = 'correct' if correct else 'native_type_or_count_mismatch'
        else:
            # Semantic verdicts from reading every final; no substring oracle.
            identity_fail = row['case_id'] in {'identity-name-en', 'identity-who-en'} and row['arm'] != 'translate_draft'
            ram_fail = row['case_id'] == 'knowledge-en' and (
                (name == 'language-repair596' and row['arm'] == 'candidate')
                or (name != 'language-repair596' and row['arm'] in {'original', 'combined_user_packet'}))
            correct = not identity_fail and not ram_fail and choice['finish_reason'] == 'stop'
            reason = 'correct' if correct else 'truncated' if choice['finish_reason'] == 'length' else 'wrong_language'
        counts[row['arm']] += bool(correct)
        adjudication.append({'case_id': row['case_id'], 'arm': row['arm'], 'verdict': reason,
                             'correct': bool(correct), 'finish_reason': choice['finish_reason'],
                             'public_content': wire, 'reasoning_chars': len(choice['message'].get('reasoning_content', '')),
                             'completion_tokens': row['response']['usage']['completion_tokens'], 'seconds': row['seconds']})
    write(private / 'adjudication.json', adjudication)
    report = []
    for request, result in zip(requests, adjudication):
        assert request['case_id'] == result['case_id'] and request['arm'] == result['arm']
        report += [f"## {result['case_id']} · {result['arm']}",
                   '```json\n' + json.dumps(request['payload'], ensure_ascii=False, indent=2) + '\n```',
                   result['public_content'], result['verdict'],
                   f"finish={result['finish_reason']}; reasoning_chars={result['reasoning_chars']}; tokens={result['completion_tokens']}"]
    (private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'comparison': name, 'correct_by_arm': dict(counts),
              'per_arm_total': len(responses)//2, 'native_request_type_correct': dict(native_type_counts),
              'verdict': notes[name], 'adopted': False, 'resources': resources,
              'private_hashes': {p: sha(private/p) for p in ['requests.jsonl', 'responses.jsonl', 'adjudication.json', 'RESULT.md']},
              'survey': {'covered': 16, 'open': 726, 'not_applicable': 0}, 'ui_or_voice_credit': False}
    write(out / 'RESULT.json', result)
    note = f"# Comparación {name}\n\n{notes[name]}\n\nAciertos por brazo: {dict(counts)}, sobre {len(responses)//2} por brazo. GPU{resources['gpu_peak_mib']:.3f}MiB; RAM{resources['ram_peak_mib']:.3f}MiB; {resources['seconds']:.3f}s. Sólo servidor nativo, sin UI/voz, efectos ni registro. Encuesta16/726/0.\n"
    (out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/astra-{name}/** -text\n')
    summaries.append(note)
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + '\n'.join(summaries))
print('594–601 sealed; translation601 alone qualifies for source integration, not product acceptance.')
