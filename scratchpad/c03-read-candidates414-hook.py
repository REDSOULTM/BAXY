
from baxy_mind.llm import LlmRuntime as _Runtime412
if os.environ.get('BAXY_C03_EARLY_READ412') in {'early-read', 'read-only-candidates'}:
    _catalog412 = json.loads((Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-read-candidates414-private/catalog.json').read_text(encoding='utf-8'))
    _reads412 = {c['name'] for c in _catalog412['capabilities'] if c['risk'] == 'read_only'}
    _prior_decide412 = _Runtime412.decide_turn
    def _early_read412(self, text, candidates, *, history=None, evidence=None):
        primary = _prior_decide412(self, text, candidates, history=history, evidence=evidence)
        if (getattr(self, '_native_tool_policy_enabled', False)
            and primary.get('mode') == 'conversation'
            and primary.get('conversation_kind') in {'knowledge', 'social'}
            and not primary.get('effect_operations') and candidates):
            read_candidates = [c for c in candidates if c['name'] in _reads412] if os.environ.get('BAXY_C03_EARLY_READ412') == 'read-only-candidates' else candidates
            if not read_candidates:
                return primary
            second = _prior_decide412(self, text, read_candidates[:4], history=history, evidence=evidence)
            operations = second.get('effect_operations')
            if (second.get('mode') in {'action', 'plan'} and isinstance(operations, list)
                and operations and all(name in _reads412 for name in operations)):
                return second
        return primary
    _Runtime412.decide_turn = _early_read412
