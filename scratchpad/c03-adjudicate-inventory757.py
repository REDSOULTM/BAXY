"""Adjudicate both frozen inventory arms without another model request."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.llm import _payload_fact_defect

private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-projection757-private'
planned = json.loads((private / 'planned.json').read_text(encoding='utf-8-sig'))
results = json.loads((private / 'results.json').read_text(encoding='utf-8-sig'))
rows = []
for plan, result in zip(planned, results, strict=True):
    assert plan['arm'] == result['arm']
    prompt = plan['payload']['messages'][1]['content']
    prefix, tail = prompt.split('\nsituation: ', 1)
    observation, _ = json.JSONDecoder().raw_decode(tail)
    response = result['response']
    choice = response['choices'][0]
    reply = choice['message']['content']
    rows.append({
        'arm': result['arm'],
        'finish_reason': choice['finish_reason'],
        'seconds': result['seconds'],
        'within4s': result['within4s'],
        'usage': response['usage'],
        'unchanged_validator_defect': _payload_fact_defect(reply, observation, prefix),
        'listed_entries': len([line for line in reply.splitlines() if line.startswith('- ')]),
        'observed_entries': len(observation['seen']['windows']),
        'reply_sha256': hashlib.sha256(reply.encode('utf-8')).hexdigest(),
    })
receipt = {
    'arms': rows,
    'manual_adjudication': {
        'captured': 'Truncated mid-list; no complete page or page-scope disclosure.',
        'identity_projection': 'All20 entries and multiplicity represented, including shell identities rendered as Explorador de archivos. Total24 preserved, but no explicit disclosure that this is a partial20-entry page: still missing_fact, not an accepted answer.',
    },
    'conclusion': 'Projection removes unrequested detail and truncation, but has not repaired complete truthfulness. No product adoption or survey credit.',
}
out = ROOT / 'artifacts/comprobaciones/C03/INVENTORY_PROJECTION757/ADJUDICATION.json'
assert not out.exists()
out.write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps(receipt, ensure_ascii=False))
