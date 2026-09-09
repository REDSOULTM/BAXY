"""Isolate whether schema tokens obscure operation meaning in E5 retrieval."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.__main__ import configure_tools
from baxy_mind.planner import PlannerCatalog
from baxy_mind.router import SemanticEncoder, MODEL_NAME, MODEL_REVISION

out = root / 'artifacts/comprobaciones/C03/astra-retrieval270'
out.mkdir(exist_ok=False)
path = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json'
hello = json.loads(path.read_text(encoding='utf-8'))
inputs = ['Tengo en mente que abras steam', 'abre steam', 'Si, abre steam']
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'inputs': inputs,
    'hypothesis': 'Schema argument metadata obscures application opening semantics; compare exact catalogue descriptions without schema suffix, keeping operation name and ranking.',
    'method': 'Current E5 CPU, frozen Core262 catalog, development literals. No native LLM or effects; no source change. One difference: remove schema suffix from passage documents.',
    'encoder': MODEL_NAME, 'encoderRevision': MODEL_REVISION,
    'catalogSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'inheritance': ['astra-retrieval261/RESULT.json', 'astra-selector-catalog67/PREREG.json'],
    'criteria': 'app.open retained top28 for all three literals; larger regression required before adoption.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
start = time.monotonic()
encoder = SemanticEncoder()
catalog = PlannerCatalog(configure_tools(hello['capabilities']), encoder=encoder.encode)
original_vectors = catalog._tool_vectors
original_documents = catalog._tool_documents
plain_documents = tuple(f'{tool.name}. {tool.description}' for tool in catalog.tools)
plain_vectors = encoder.encode(plain_documents, prefix='passage')
rows = []
for variant, documents, vectors in [('original', original_documents, original_vectors), ('without_schema', plain_documents, plain_vectors)]:
    catalog._tool_vectors = vectors
    for text in inputs:
        scores = catalog._semantic_tool_scores(text)
        names = sorted(scores, key=scores.get, reverse=True)
        shortlist = [tool.name for tool in catalog.shortlist(text)]
        row = {'variant': variant, 'input': text, 'appOpenRank': names.index('app.open') + 1,
            'appOpenVisible': 'app.open' in shortlist, 'shortlist': shortlist}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
(out / 'RESULT.json').write_text(json.dumps({'seconds': time.monotonic() - start, 'rows': rows}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
