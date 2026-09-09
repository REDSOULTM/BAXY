"""Read-only comparison of current and contextual catalogue retrieval."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root/'src')]
from scripts.measure_mind_budget import current_core_catalog_snapshot
from baxy_mind.__main__ import configure_tools, _turn_evidence_query
from baxy_mind.planner import PlannerCatalog

out = root/'artifacts/comprobaciones/C03/astra-context-candidates643'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-context-candidates643-private'
out.mkdir(exist_ok=False); private.mkdir(exist_ok=False)
def write(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
core = root/'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/baxy-core.exe'
write(out/'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'source_modified': False,
    'method': 'Compare lexical candidates with current input only and the existing bounded evidence query. No model calls, dispatch, history rewriting in a model prompt, or effect authority. Use actual product642 history and independent topic-shift controls. Candidate presence alone is not behavior coverage.',
    'inheritance': ['product640 and642 candidate lists omit window.application.status for named follow-ups', 'biblioteca/gemma4-agent/documentacion/07_latencia/research/4_contexto.md: context for ellipsis rather than every utterance', 'src/baxy_mind/llm.py: product360 already rejected quoting previous requests as current commands'],
    'research': ['https://aclanthology.org/2022.emnlp-main.311/', 'https://aclanthology.org/2024.findings-acl.792/'],
    'research_limit': 'Conversational retrieval papers motivate relevant context and warn about noisy history. They do not validate a BAXY retrieval strategy or authorize old effects.',
    'core_sha256': sha(core),
    'sources': {p: sha(root/p) for p in ['src/baxy_mind/planner.py', 'src/baxy_mind/__main__.py']},
})
capabilities, _, _ = current_core_catalog_snapshot(core)
tools = configure_tools(capabilities)
write(private/'tools.json', tools)
catalog = PlannerCatalog(tools)
previous = private.parent/'C03-count-product642-private'
panel = json.loads((previous/'panel.json').read_text(encoding='utf-8'))
with (previous/'capture/events.jsonl').open(encoding='utf-8-sig') as f:
    finals = [r for line in f if (r := json.loads(line)).get('type') == 'terminal']
history = []
cases = []
for i, (case, final) in enumerate(zip(panel, finals), 1):
    if i in [15, 16, 17, 18]:
        cases.append({**case, 'history': history[-4:]})
    history += [{'role': 'user', 'content': case['text']}, {'role': 'assistant', 'content': final['final']}]
for case_id, text, expected in [
    ('shift-time-es', '¿Qué hora es?', 'system.time'),
    ('shift-volume-en', 'Set the volume to 30', 'audio.volume'),
    ('shift-network-es', '¿Tengo conexión a internet?', 'network.status'),
    ('shift-files-en', 'List my files in Downloads', 'file.list'),
]:
    cases.append({'case_id': case_id, 'text': text, 'operation': expected, 'history': history[-4:]})
results = []
for case in cases:
    query = _turn_evidence_query(case['text'], case['history'])
    current = [t.name for t in catalog.shortlist(case['text'])]
    context = [t.name for t in catalog.shortlist(query)]
    r = {**case, 'query': query, 'current': current, 'context': context,
         'current_rank': current.index(case['operation'])+1 if case['operation'] in current else None,
         'context_rank': context.index(case['operation'])+1 if case['operation'] in context else None}
    results.append(r)
    print(json.dumps({k: r[k] for k in ['case_id', 'operation', 'current_rank', 'context_rank']}, ensure_ascii=False))
write(private/'retrieval.json', results)
write(out/'RESULT.json', {'cases': len(results), 'retrieval': 'lexical',
    'ranks': [{k: r[k] for k in ['case_id', 'operation', 'current_rank', 'context_rank']} for r in results],
    'private_hashes': {'tools.json': sha(private/'tools.json'), 'retrieval.json': sha(private/'retrieval.json')},
    'source_modified': False, 'model_or_product_credit': False})
