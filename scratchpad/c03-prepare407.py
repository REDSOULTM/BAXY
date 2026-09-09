from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-account-scope405.py').read_text(encoding='utf-8')
for a, b in [('astra-account-scope405', 'astra-retrieval-startup407'), ('C03-account-scope405-private', 'C03-retrieval-startup407-private'), ('catalog405', 'catalog407'), ('close405', 'close407')]:
    source = source.replace(a, b)
source = source.replace("for variant in ['baseline', 'identity-scope']:", "for variant in ['identity-scope']:")
source = source.replace("(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')", "hook_source += (root / 'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8')\n(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')")
method = 'Same nine fixed cases405, same source397/404 and scope-only diagnostic hook405, same model/catalog/sampler. Read-only startup observers record actual E5 readiness, corpus build and semantic resources. Wait for semantic resources or 195s terminal deadline before deciding the nine cases; no fake readiness, forced tools, descriptor change, effects or promotion. Distinguish cold-start lexical from loaded retrieval behavior.'
reason = '405 audit explicitly records lexical retrieval.406b real CPU E5 loads in20.234s and builds resources in3.547s: accountES rank1 (lexical absent), two username variants still absent. Diagnose actual startup ordering before adopting any source change.'
source = '\n'.join('    '+repr('method')+': '+repr(method)+',' if line.startswith("    'method':") else '    '+repr('reason')+': '+repr(reason)+',' if line.startswith("    'reason':") else line for line in source.splitlines()) + '\n'
needle = "        for case in cases:\n"
replacement = '''        evidence_status = client.request({'id': 'evidence407-initial', 'type': 'turn.evidence.status'}, 10)
        (out / 'evidence-initial.json').write_text(json.dumps(evidence_status, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
        wait_start = time.monotonic()
        while time.monotonic() - wait_start < 195:
            telemetry = private / 'startup-observer.jsonl'
            observed = [json.loads(s) for s in telemetry.read_text(encoding='utf-8').splitlines()] if telemetry.exists() else []
            if any(r['event'] == 'resources_built' and r.get('semantic') for r in observed):
                break
            if any(r['event'] in {'router_failed', 'resources_failed'} for r in observed):
                break
            time.sleep(0.25)
        (out / 'wait.json').write_text(json.dumps({'seconds': time.monotonic() - wait_start, 'observed': observed}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
        evidence_status = client.request({'id': 'evidence407-after', 'type': 'turn.evidence.status'}, 10)
        (out / 'evidence-after.json').write_text(json.dumps(evidence_status, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
        print(json.dumps({'startup_wait_seconds': round(time.monotonic() - wait_start, 3), 'events': observed}), flush=True)
        for case in cases:
'''
assert needle in source
source = source.replace(needle, replacement)
target = root / 'scratchpad/c03-retrieval-startup407.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
print('407 prepared; no source change')
