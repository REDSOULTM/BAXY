"""Preregister a single-message ablation using the existing paired selector controls."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'K2_HORIZON_SELECTOR700'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-selector-ablation700-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
source=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-k2-comparison696-private/panel.json'
assert sha(source)=='5a5aa1d46bbc60eb757566ac535c89ebf0755f4da7ed4f03b7215241787cea76'
original=[r for r in read(source) if r['id'].startswith('select-')]
assert len(original)==20
policy=original[0]['payload']['messages'][0]
assert policy['role']=='system'
cases=copy.deepcopy(original)
for row in cases:
    assert row['payload']['messages'][0]==policy
    assert sum(m['role']=='system' for m in row['payload']['messages'])==1
    row['payload']['messages'].pop(0)
write(private/'panel.json',cases)
baselines={}
for family,tag in [('qwen','qwen-documented1'),('k2','37-q4-high-parser698-1')]:
    public=base/'K2_HORIZON_COMPARISON696'/('run-'+tag)
    old_private=Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-k2-run696-{tag}-private'
    requests=[json.loads(line) for line in (old_private/'requests.jsonl').read_text(encoding='utf-8').splitlines()][:20]
    assert [r['case'] for r in requests]==[r['id'] for r in original]
    expected=[]
    changes=[]
    for request in requests:
        without=copy.deepcopy(request)
        assert without['payload']['messages'][0]==policy
        without['payload']['messages'].pop(0)
        expected.append(without)
        before=copy.deepcopy(request['payload'])
        before['messages'].pop(0)
        assert before==without['payload']
        changes.append(dict(case=request['case'],only_change='Removed exactly the first system message.',
            before_payload_sha256=digest(request['payload']),after_payload_sha256=digest(without['payload'])))
    write(private/(family+'-expected-requests.json'),expected)
    baselines[family]=dict(tag=tag,preregistration_path=public.relative_to(root).as_posix()+'/PREREG.json',
        preregistration_sha256=sha(public/'PREREG.json'),
        expected_requests_sha256=sha(private/(family+'-expected-requests.json')),
        existing_adjudication_sha256=sha(public/'ADJUDICATION.json'),paired_changes=changes)
plan=dict(utc=datetime.now(timezone.utc).isoformat(),cases=20,panel_sha256=sha(private/'panel.json'),
    original_panel_sha256=sha(source),removed_system_characters=len(policy['content']),removed_system_sha256=digest(policy),
    baselines=baselines,case_ids=[r['id'] for r in original],
    method='Reuse the first20 selector outputs from each existing baseline; run their20 paired counterparts with only NATIVE_TOOL_POLICY_PROMPT removed. Effective payloads and normalized server commands must match exactly outside that one message and dynamic port/log paths. Same weights, backend package, sampling, seed, context, KV, limits and order. All20 constitute the complete selector category; no arbitrary subset of successes.',
    limits='This is a conditional selector-policy ablation with unchanged BAXY catalogs and histories, not an independent generic tool benchmark. Arguments remain empty by design; no argument extraction, kernel, providers, effects or product acceptance. Catalog absence in select-network-internet-es is reported separately. Historical single-seed controls are reused; this is development evidence, not a randomized causal estimate.',
    scoring='Apply original frozen criteria to tool names/order/abstention and complete visible output; no automatic credit from matching one function name. Keep errors/empty replies and unsupported effect claims. No survey coverage.')
write(out/'PLAN.json',plan)
print(json.dumps(dict(cases=20,planned_new_calls=40,policy_characters=len(policy['content']),panel_sha256=plan['panel_sha256'])))
