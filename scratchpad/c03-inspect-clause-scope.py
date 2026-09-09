import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import effect_intent as e

for text in ["I don't mind, tell me the time", 'tell me the time', 'no me molesta, dime la hora', 'dime la hora', 'no me molesta, poné música',
             'no abras Steam, dime la hora', 'no me digas la hora', 'no abras Steam y abre Chrome']:
    folded = e._strip_request_envelope(e._fold(text))
    ops = ['system.time', 'media.play.query', 'app.launch']
    result = e.resolve_explicit_effects(text, ops)
    print({name: getattr(e, name)(folded) for name in ['_is_meta_or_tool_denial', '_has_contradictory_correction', '_is_direct_request', '_other_device_effect_scope']})
    print(json.dumps({'text': text, 'folded': folded, 'clauses': e._request_clauses(folded), 'intent': repr(result), 'unresolved': repr(e.unresolved_compound_contract(text, ops, resolved_intent=result))}, ensure_ascii=False))
