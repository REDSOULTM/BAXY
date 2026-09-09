"""Measure typed catalog-entity retrieval without changing user/model input."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.__main__ import configure_tools, configure_application_catalog
from baxy_mind.effect_intent import build_application_catalog_index, _fold
from baxy_mind.planner import PlannerCatalog
from baxy_mind.router import SemanticEncoder

out = root / 'artifacts/comprobaciones/C03/astra-entity276'
out.mkdir(exist_ok=False)
hello = json.loads((Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json').read_text(encoding='utf-8'))
apps = build_application_catalog_index(configure_application_catalog(hello['apps']))
inputs = ['Tengo en mente que abras steam', 'abre steam', 'Si, abre steam']
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'Exact app-name entity tokens dominate E5 toward Steam game operations; replacing only an authenticated app span with its type in the retrieval query can preserve requested verb semantics.',
    'method': 'Three reused development literals, actual catalog occurrence pattern, original E5/documents/ranking. Compare full request with typed-entity query only. This does not replace model/user text or grant effect authority.',
    'criteria': 'app.open reaches shortlist and ranks ahead of unrelated games for all three inputs. Broader regression required; no product adoption yet.',
    'entityType': 'installed application', 'inputs': inputs}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
encoder = SemanticEncoder()
catalog = PlannerCatalog(configure_tools(hello['capabilities']), encoder=encoder.encode)
rows = []
for text in inputs:
    typed = apps.occurrence_pattern.sub('installed application', _fold(text))
    for variant, query in [('original', text), ('typed_entity', typed)]:
        scores = catalog._semantic_tool_scores(query)
        ranked = sorted(scores, key=scores.get, reverse=True)
        shortlist = [tool.name for tool in catalog.shortlist(query)]
        row = {'input': text, 'variant': variant, 'query': query, 'appOpenSemanticRank': ranked.index('app.open') + 1,
            'appOpenShortlistRank': shortlist.index('app.open') + 1 if 'app.open' in shortlist else None,
            'shortlist': shortlist}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
(out / 'RESULT.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
