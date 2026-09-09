"""Adjudicate completed native497 without executing a model or changing source."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-gemma-original497'
def read_rows(path):
    return [json.loads(line) for line in path.open(encoding='utf-8-sig')]
def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
rows = read_rows(out / 'replies.jsonl')
prior = {r['id']: r for r in read_rows(base / 'astra-gemma-parse494/replies.jsonl')}
assert len(rows) == 14
adjudications = []
for row in rows:
    response = row['response']
    message = response['choices'][0]['message']
    calls = [c['function'] for c in message.get('tool_calls', [])]
    arguments = [json.loads(c['arguments']) for c in calls]
    owner51 = row['id'].startswith('owner51')
    wrong_state = owner51 and any(a.get('state') is True for a in arguments)
    zero_violation = row['variant'] == 'zero' and any(arguments)
    checks = {
        'wrong_mute_state': wrong_state,
        'violates_declared_zero_argument_interface': zero_violation,
        'unmute_polarity_unproved': owner51 and row['variant'] == 'zero' and not any(arguments),
        'stage_like_prose': row['id'] == 'negative-only' and row['variant'] == 'typed',
    }
    expected = (['baxy_audio__volume', 'baxy_audio__mute'] if owner51 or row['id'] == 'volume-unmute'
                else ['baxy_audio__mute'] if row['id'].startswith('owner46') else [])
    assert [c['name'] for c in calls] == expected
    verbose = response['__verbose']
    assert verbose['stop_type'] == 'eos' and verbose['truncated'] is False
    item = {'id': row['id'], 'variant': row['variant'], 'calls': calls,
            'content': message.get('content'), 'checks': checks,
            'stop': 'eos', 'truncated': False}
    if row['variant'] == 'typed' and row['id'] in prior:
        item['rendered_prompt_matches_published494'] = (
            verbose['prompt'] == prior[row['id']]['response']['__verbose']['prompt'])
        assert item['rendered_prompt_matches_published494']
    adjudications.append(item)
write(out / 'ADJUDICATION.json', adjudications)
resources = json.loads((out / 'RESOURCES.json').read_text(encoding='utf-8-sig'))
write(out / 'RESULT.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'session': 98048, 'exit': 0,
    'cases': len(rows), 'all_expected_operation_names_without_extras': True,
    'wrong_contextual_mute_state': sum(a['checks']['wrong_mute_state'] for a in adjudications),
    'zero_argument_schema_violations': sum(a['checks']['violates_declared_zero_argument_interface'] for a in adjudications),
    'matching_rendered_prompts_with494': sum(a.get('rendered_prompt_matches_published494', False) for a in adjudications),
    'maximum_completion_tokens': max(r['response']['usage']['completion_tokens'] for r in rows),
    'maximum_total_tokens': max(r['response']['usage']['total_tokens'] for r in rows),
    'resources': resources, 'adopted': False,
    'conclusion': 'Original Gemma avoids the repeated additional calls of the published checkpoint under native grammar on this panel, including three identical rendered prompts. It still inverts unmute in the contextual compound, emits arguments in the zero-argument interface, and has one stage-like no-action response. No 14/14 product claim.',
    'next': 'Repair independently reproduced positive adversative clause loss498, then contextual clarification transport. No more sampler or grammar sweeps without a new cause.'
})
lines = ['# Gemma original: comparación nativa 497', '',
         'El checkpoint original evita las operaciones adicionales observadas en el publicado. Tres prompts renderizados coinciden exactamente con 494; ambos usan gramática nativa y el perfil documentado de Google. Esto acredita esta comparación acotada, no la aceptación del producto.', '',
         'La petición contextual de volumen y desmute sigue invirtiendo el booleano en tres respuestas. Cuatro respuestas violan la interfaz declarada sin argumentos. La única selección contextual con argumentos vacíos no acredita todavía nivel ni polaridad. `state=true` silencia y `state=false` reactiva.', '',
         '| Caso | Interfaz | Resultado literal | Observación |', '|---|---|---|---|']
for a in adjudications:
    literal = json.dumps(a['calls'], ensure_ascii=False) if a['calls'] else a['content']
    observations = ', '.join(k for k, v in a['checks'].items() if v) or 'Propuesta nativa correcta; ejecución no probada'
    lines.append(f"| {a['id']} | {a['variant']} | {literal.replace('|', '/')} | {observations} |")
lines += ['', f"RAM: {resources['ram_peak_mib']:.3f} MiB; VRAM: {resources['gpu_peak_mib']:.3f} MiB; tiempo: {resources['seconds']} s. Medición del servidor y conductor nativo, no de BAXY completo. EOS y sin truncamiento en las 14 respuestas.", '',
          'No se modifica el runtime registrado. El siguiente trabajo es la pérdida de cláusulas y el contexto de aclaración en el producto; no se repite un barrido de parámetros.', '']
(out / 'RESULT.md').write_text('\n'.join(lines), encoding='utf-8')
write(out / 'PINS.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
print(json.dumps({'closed': 497, 'cases': 14, 'adopted': False}))
