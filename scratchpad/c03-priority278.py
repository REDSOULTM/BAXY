"""Price authenticated-app retrieval priority against known development controls."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import sys
import urllib.request

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.__main__ import configure_tools, configure_application_catalog, _shortlist_with_required_effects
from baxy_mind.effect_intent import build_application_catalog_index, _fold
from baxy_mind.planner import PlannerCatalog
from baxy_mind.router import SemanticEncoder
from baxy_mind.llm import LlmRuntime

out = root / 'artifacts/comprobaciones/C03/astra-priority278'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
hello = json.loads((private / 'C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
apps = build_application_catalog_index(configure_application_catalog(hello['apps']))
corpus = [json.loads(line) for line in (root / 'artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl').read_text(encoding='utf-8').splitlines()]
cases = [row for row in corpus if apps.occurrence_pattern.search(_fold(row['text']))]
wire = [json.loads(line) for line in (private / 'C03-ui263-private/http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
old = next(row['payload'] for row in wire if row.get('stage') == 'request' and row.get('id') == 5)
history = json.loads(old['messages'][-1]['content'])['previous_dialogue_for_references_only']
cases += [{'case_id': f'owner-{index}', 'text': text, 'expected_operations': ['app.open'], 'history': history}
          for index, text in enumerate(['Tengo en mente que abras steam', 'abre steam', 'Si, abre steam'], 1)]
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Authenticated local application name supplies direct app.open identity evidence for retrieval priority; model still chooses requested effect among28.',
    'method': 'All14 matching rows from the124 historical development corpus plus3 reused owner controls. Same E5 and original request/history/native selector; compare original shortlist with app.open moved/included first using existing merge primitive. No source edit or effects.',
    'criteria': 'Owner3 selects app.open; no previously correct control is lost. Expected operation arrays in original corpus can contain alternatives and are reported literally, not silently scored as compound.',
    'cases': cases, 'count': len(cases), 'freshAcceptance': False, 'backendPid': 89232}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
class Runtime(LlmRuntime):
    def __init__(self):
        self.last_post = None
    def _post(self, payload):
        with urllib.request.urlopen('http://127.0.0.1:57485/slots', timeout=5) as response:
            assert not any(row['is_processing'] for row in json.load(response)), 'Backend busy.'
        request = urllib.request.Request('http://127.0.0.1:57485/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        self.last_post = {'payload': payload, 'response': result}
        return result
runtime = Runtime()
encoder = SemanticEncoder()
catalog = PlannerCatalog(configure_tools(hello['capabilities']), encoder=encoder.encode)
contracts = {tool.name: {'description': tool.description} for tool in catalog.tools}
results = []
for case in cases:
    before = catalog.shortlist(case['text'])
    after = _shortlist_with_required_effects(before, ('app.open',), catalog)
    for variant, shortlist in [('before', before), ('app_identity_priority', after)]:
        decision = runtime._post_native_tool_selection(case['text'], [tool.name for tool in shortlist], contracts, case.get('history', []))
        row = {'case_id': case['case_id'], 'input': case['text'], 'expected_operations': case['expected_operations'],
            'variant': variant, 'decision': decision, 'post': runtime.last_post}
        results.append(row)
        (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({key:row[key] for key in ('case_id', 'variant', 'expected_operations', 'decision')}, ensure_ascii=False), flush=True)
