"""Compare frozen/current speech-act readers without model or desktop actions."""
from pathlib import Path
from datetime import datetime, timezone
import dataclasses
import hashlib
import importlib.util
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import __main__ as mind, effect_intent as current

out = root / 'artifacts/comprobaciones/C03/astra-acknowledgement266'
baseline_path = out/'before/effect_intent.py'
spec = importlib.util.spec_from_file_location('baxy_mind._c03_before266', baseline_path)
baseline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = baseline
spec.loader.exec_module(baseline)
catalog_path = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json'
catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
apps = mind.configure_application_catalog(catalog['apps'])
game_entries = mind.configure_game_catalog(catalog['games'])
operations = tuple(item['name'] for item in catalog['capabilities'])
inputs = ['abre steam', 'Tengo en mente que abras steam', 'Si, abre steam']
def inspect(module, text):
    games = module.build_game_catalog_index(game_entries)
    resolved = module.resolve_explicit_effects(text, operations, apps, games)
    contract = module.unresolved_compound_contract(text, operations, apps, games, resolved_intent=resolved)
    return {'folded': module._strip_request_envelope(module._fold(text)),
        'intent': dataclasses.asdict(resolved) if resolved else None,
        'app': module.resolve_application_catalog_app_id(text, apps),
        'compound': dataclasses.asdict(contract) if contract else None}
rows = [{'input': text, 'before': inspect(baseline, text), 'after': inspect(current, text)} for text in inputs]
# The following is the actual post-selection domain guard, not a simulated LLM.
intent = current.resolve_explicit_effects(inputs[-1], operations, apps, game_entries)
decision = {'mode':'action', 'operation':'app.open', 'effect_operations':['app.open'],
    'effect_count':'one', 'effect_verification':'one', 'question':'', 'conversation_kind':''}
guarded = mind.apply_operation_domain_grounding_veto(decision, inputs[-1], intent, apps,
    game_catalog=current.build_game_catalog_index(game_entries))
result = {'utc': datetime.now(timezone.utc).isoformat(), 'rows': rows,
    'domainGuard': guarded,
    'limitations': 'Helpers only; no native inference, Core effect, public UI, or audio acceptance. Owner264 remains untouched.',
    'sourceAfter': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
        ['src/baxy_mind/effect_intent.py', 'tests/test_effect_intent.py']}}
target = out/('REPLAY_FINAL.json' if '--final' in sys.argv else 'REPLAY.json')
if target.exists():
    raise RuntimeError('Replay evidence already exists')
target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'rows':rows, 'domainGuard':guarded}, ensure_ascii=False, indent=2))
