# Diagnostic only: vary retrieval query; retain every production decision guard.
from baxy_mind.planner import PlannerCatalog as _Catalog489
_private489 = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-context-retrieval489-private'
_cases489 = json.loads((_private489 / 'cases.json').read_text(encoding='utf-8'))
_context489 = {}
for _case489 in _cases489:
    _previous489 = next((row['content'] for row in reversed(_case489['history'])
                         if row['role'] == 'user'), None)
    if _previous489:
        _context489[_case489['request']] = _previous489
_shortlist489 = _Catalog489.shortlist

def _context_shortlist489(self, objective):
    original = _shortlist489(self, objective)
    previous = _context489.get(objective)
    if previous is None:
        return original
    query = previous + '\n' + objective
    changed = _shortlist489(self, query)
    with (_private489 / 'retrieval-intervention.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'request': objective, 'query': query,
                                 'original': [tool.name for tool in original],
                                 'changed': [tool.name for tool in changed]}, ensure_ascii=False) + '\n')
    return changed

_Catalog489.shortlist = _context_shortlist489
