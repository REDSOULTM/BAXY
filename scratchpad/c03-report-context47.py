from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
lines = ['# C03 — contexto de conocimiento, respuestas literales47', '',
         'Diagnóstico técnico; no reserva humana ni aprobación C03. Dictamen y límites en ASTRA-TRAMO-47.md.', '']
for folder in ['astra-knowledge-context47', 'astra-wire-replay47']:
    lines += [f'## {folder}', '']
    for row in [json.loads(s) for s in (base / folder / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]:
        choice = row['response']['choices'][0]
        lines += [f'### {row["stage"]}: {row["text"]}', '',
                  str(choice['message'].get('content', '')), '', f'finish_reason: {choice.get("finish_reason")}', '']
for folder in ['astra-wire-context47', 'astra-topic-context47']:
    lines += [f'## {folder}', '']
    for row in json.loads((base / folder / 'paired.json').read_text(encoding='utf-8')):
        lines += [f'### {row["turnId"]}', '', f'Entrada: {row["request"]}', '', f'Respuesta: {row["final"]}', '']
(base / 'PRUEBAS_CONTEXTO_CONOCIMIENTO47.md').write_text('\n'.join(lines), encoding='utf-8')
files = ['src/baxy_mind/request_reading.py', 'src/baxy_mind/effect_intent.py', 'src/baxy_mind/llm.py',
         'src/baxy_mind/__main__.py', 'src/baxy_mind/voice_output.py',
         'tests/test_request_reading.py', 'tests/test_turn_policy.py']
pins = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'EN_CURSO',
        'candidate': 'Terminal style modifiers use existing new-topic context scope; no model/prompt change.',
        'product': 'astra-topic-context47:10/10 useful technical turns; not acceptance.',
        'tests': {'pass': 2945, 'subtests': 115, 'skips': 0},
        'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files}}
(base / 'TRAMO47_PINS.json').write_text(json.dumps(pins, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote literal comparison and source47 pins.')
