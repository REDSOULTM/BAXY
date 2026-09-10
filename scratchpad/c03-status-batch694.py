"""Evaluate shared status source693 on the exact frozen73-turn product panel689."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-status-batch694-private'
gate=(Path(os.environ['TEMP'])/'c03-shared-status693-full.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in gate, 'Full693 must pass before product evaluation'
assert psutil.virtual_memory().available>=2700*2**20
private.mkdir(exist_ok=False)
old=private.parent/'C03-status-batch689-private/panel.json'
(private/'panel.json').write_bytes(old.read_bytes())
panel=json.loads(old.read_text(encoding='utf-8'))
assert len(panel)==73
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
registry=private.parent/'C03-survey-requirements336-private/requirements.jsonl'
plan={'utc':datetime.now(timezone.utc).isoformat(),'parent_plan':'STATUS_BATCH689_PLAN.json',
 'parent_plan_sha256':sha(base/'STATUS_BATCH689_PLAN.json'),'same73_inputs_and_order':True,
 'panel_sha256':sha(old),'requirements_sha256':sha(registry),
 'survey_counts_before':{'covered':26,'open':716,'not_applicable':0},
 'changes':'Shared source693: decimal measurement projection, independent installed RAM observation and wifi.status read-only policy. Same model, runtime, per-turn criteria and campaign resource ceilings. No clearing pending state between turns.',
 'effect_scope':'Read-only status in hidden diagnostic product. No UI/voice credit, no user data sent externally.',
 'criteria':'Original689 criteria unchanged. Verify requested fields against fresh typed observations, installed/usable distinction, units, unknown adapters and Wi-Fi identity gap. Count all failures; no automatic survey credit.'}
plan['instrumentation'] = 'Declared before first694 execution: transparent private _post and decide_turn boundary observers inherited from521. Identical arguments, one original call, identical returned object or exception; no server flags, payload/model/candidate/output changes. Diagnostic latency includes file logging. This adds observation to689 built-in audits without changing its73 inputs/order/criteria.'
plan['instrumentation_sha256'] = sha(root/'scratchpad/c03-status694-hook/sitecustomize.py')
(base/'STATUS_BATCH694_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
source=(root/'scratchpad/c03-status-batch689.py').read_text(encoding='utf-8')
source=source[source.index("source = (root/'scratchpad/c03-conversation-regression592.py')"):]
source=source.replace('astra-status-batch689','astra-status-batch694').replace('C03-status-batch689-private','C03-status-batch694-private').replace('C03-status-profile689','C03-status-profile694')
source=source.replace('Shared published source686 product','Shared candidate source693 product after Full693')
source=source.replace('Batch diagnostic baseline, not automatic survey coverage.', 'Exact regression689 after shared quantities, installed RAM and wifi read policy changes; no automatic survey coverage.')
source=source.replace("'src/baxy_mind/window_prose_facts.py',", "'src/baxy_mind/measurement_prose_projection.py', 'src/Baxy.Kernel/Operations/ProductCatalog.cs', 'src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProbe.cs', 'src/Baxy.Core/Operations/SystemStatusHandler.cs', 'src/baxy_mind/window_prose_facts.py',")
# The inherited592 script removes521's observer. Select our private transparent
# observer instead, before the nested production driver is compiled or launched.
old_observer_removal = 'source = source.replace(old, "str(root/\'src\')")'
new_observer_selection = 'source = source.replace(old, "str(root/\'scratchpad/c03-status694-hook\')+os.pathsep+str(root/\'src\')")'
new_observer_selection += '\nsource = source.replace("registered runtime, built-in diagnostics only.", "registered runtime, built-in diagnostics plus transparent local HTTP/decision observation declared in STATUS_BATCH694_PLAN.json.")'
source = source.replace("exec(compile(source,__file__,'exec'))", "assert source.count(" + repr(old_observer_removal) + ") == 1\nsource = source.replace(" + repr(old_observer_removal) + ", " + repr(new_observer_selection) + ")\nexec(compile(source,__file__,'exec'))")
exec(compile(source,__file__,'exec'))
