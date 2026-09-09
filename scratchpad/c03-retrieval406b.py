"""Separate lexical and loaded E5 catalog ranking without an LLM or effects."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['PYTHONPATH'] = str(root / 'src')
from baxy_mind.__main__ import configure_tools, _create_planner_resources
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder, verified_encoder_snapshot_identity

out = root / 'artifacts/comprobaciones/C03/astra-retrieval406b'
out.mkdir(exist_ok=False)
previous = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-account-scope405-private'
catalog_path = previous / 'catalog.json'
cases_path = root / 'scratchpad/c03-account-scope405-cases.json'
catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
cases = json.loads(cases_path.read_text(encoding='utf-8'))['cases']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Same authenticated catalog405 and nine cases405; compare existing lexical and fully loaded E5 ranking. CPU encoder only, no LLM, effects, source edits, synonyms or promotion. No new acceptance cases consumed. Report readiness failure if it occurs; missing operation alone does not establish production readiness state.',
    'catalog': str(catalog_path), 'catalog_sha256': sha(catalog_path), 'cases_sha256': sha(cases_path),
    'source': {n: sha(root / 'src/baxy_mind' / n) for n in ['router.py', 'router_worker.py', 'planner.py', '__main__.py', 'turn_evidence.py']},
    'inheritance': ['biblioteca/gemma4-agent/documentacion/02_router/research/07_SKILL_RETRIEVAL_research.md:1-62', 'artifacts/comprobaciones/C03/retrieval270-run.log', '__main__.py:7290-7338'],
    'primary': ['https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md', 'https://arxiv.org/abs/2409.00608'],
    'criteria': 'Identity available for four direct account questions; system.status retained for three resource/version controls. Concept/prohibition measured only for visibility, never interpreted as permission. Compare actual405 candidate lists without claiming lexical use until matched.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
tools = configure_tools(catalog['capabilities'])
lexical, _ = _create_planner_resources(tools)
rows = []
def measure(label, planner):
    for case in cases:
        started = time.monotonic()
        names = [t.name for t in planner.shortlist(case['request'])]
        target = 'system.identity' if case['id'].startswith(('account-', 'username-')) else 'system.status' if case['id'] in {'os-version', 'os-memory', 'cpu'} else None
        result = {'variant': label, 'id': case['id'], 'request': case['request'], 'ranks_semantically': planner.ranks_semantically,
                  'target': target, 'target_rank': names.index(target) + 1 if target in names else None,
                  'seconds': round(time.monotonic() - started, 3), 'shortlist': names}
        rows.append(result)
        with (out / 'ranks.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k not in {'shortlist', 'request'}}), flush=True)
measure('lexical', lexical)
started = time.monotonic()
router = ProcessIntentRouter()
(out / 'PROCESS.json').write_text(json.dumps({'pid': os.getpid(), 'worker_owner': 'ProcessIntentRouter'}) + '\n', encoding='utf-8')
try:
    deadline = started + 60
    while time.monotonic() < deadline and not router.try_ready(1):
        if router._failed:
            raise RuntimeError('encoder failed: ' + router._failure)
    if not router.try_ready(0):
        raise TimeoutError('E5 did not initialize within 60s')
    ready_seconds = time.monotonic() - started
    identity = verified_encoder_snapshot_identity()
    encoder = RequestBudgetEncoder(router)
    build_started = time.monotonic()
    semantic, _ = _create_planner_resources(tools, encoder)
    build_seconds = time.monotonic() - build_started
    measure('semantic', semantic)
    (out / 'READINESS.json').write_text(json.dumps({'ready_seconds': ready_seconds, 'build_seconds': build_seconds, 'encoder': identity, 'device': 'cpu (source default, not a GPU measurement)'}, indent=2) + '\n', encoding='utf-8')
finally:
    router.close()
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'rows': len(rows), 'source_unchanged': all(sha(root / 'src/baxy_mind' / n) == value for n, value in prereg['source'].items())}) + '\n', encoding='utf-8')
print(json.dumps({'completed': True, 'ready_seconds': round(ready_seconds, 3), 'build_seconds': round(build_seconds, 3)}), flush=True)
