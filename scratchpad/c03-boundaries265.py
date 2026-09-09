"""Read-only speech-act boundaries with frozen Core262 catalogs, no inference."""
from pathlib import Path
from datetime import datetime, timezone
import dataclasses
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import __main__ as mind, effect_intent as effect

out = root / 'artifacts/comprobaciones/C03/astra-boundaries265'
out.mkdir(exist_ok=True)
if (out/'PREREG.json').exists():
    raise RuntimeError('Evidence already exists')
catalog_path = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-app-catalog262-private/HELLO_CATALOGS.json'
catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
apps = mind.configure_application_catalog(catalog['apps'])
games = effect.build_game_catalog_index(mind.configure_game_catalog(catalog['games']))
operations = frozenset(tool['function']['canonical_name'] for tool in mind.configure_tools(catalog['capabilities']))
inputs = ['abre steam', 'Tengo en mente que abras steam', 'Si, abre steam']
def save(name, value):
    (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
save('PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Three owner literals reused as development, frozen Core262 catalog. No LLM, CPU encoder, UI, or effects. Inspect actual boundary predicates before any source change.',
    'inputs': inputs, 'catalogSha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
    'source': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
        ['src/baxy_mind/__main__.py', 'src/baxy_mind/effect_intent.py']}})
rows = []
for text in inputs:
    folded = effect._strip_request_envelope(effect._fold(text))
    intent = effect.resolve_explicit_effects(text, operations, apps, games)
    row = {'input': text, 'folded': folded,
        'explicitIntent': dataclasses.asdict(intent) if intent else None,
        'resolvedApp': effect.resolve_application_catalog_app_id(text, apps),
        'catalogUnavailable': mind._catalog_unavailable_turn_decision(text, intent, apps, games),
        'unresolvedCompound': effect.unresolved_compound_contract(text, operations, apps, games, resolved_intent=intent),
        'authoritative': effect.effect_request_is_authoritative(text),
        'knownUnsupported': effect.known_unsupported_effect_request(text, operations),
        'stableNoEffect': mind._explicit_stable_no_effect_turn_decision(text, []),
        'nonAction': effect.explicit_non_action_frame(text),
        'clauses': effect._request_clauses(folded),
        'contradictoryCorrection': effect._has_contradictory_correction(folded, operations)}
    rows.append(row)
save('RESULT.json', rows)
print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
