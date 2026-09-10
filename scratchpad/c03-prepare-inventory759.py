"""Test explicit page semantics after unchanged count metadata remained ambiguous."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-inventory-projection757.py').read_text(encoding='utf-8-sig')
source = source.replace('757', '759')
source = source.replace('"""Same captured inventory and profile; change only the inventory writing clause."""',
                        '"""Hold identities and prompt fixed; describe the existing page facts explicitly."""')
source = source.replace("planned = [{'arm': 'captured', 'payload': baseline}, {'arm': 'identity_projection', 'payload': candidate}]", """baseline = copy.deepcopy(candidate)
page = projected['seen']
assert page['complete'] is True and type(page['totalCount']) is int
page['returnedPageScope'] = {
    'windowsListedOnThisPage': page['count'],
    'totalWindowsInSelectedInventory': page['totalCount'],
    'thisListIncludesEveryWindowInSelectedInventory': page['offset'] == 0 and page['count'] == page['totalCount'],
}
candidate['messages'][1]['content'] = prefix + '\\nsituation: ' + json.dumps(projected, ensure_ascii=False) + tail[end:]
assert candidate['messages'][0] == baseline['messages'][0]
planned = [{'arm': 'identity_projection', 'payload': baseline}, {'arm': 'explicit_page_semantics', 'payload': candidate}]""")
source = source.replace("'change': INSTRUCTION", "'change': 'Same identity projection and original prompt; add only factual returned-page scope derived from the preserved typed counts'")
source = source.replace("Projection intervention after instruction-only754-756 did not complete either list.",
                        "757 identity projection completed20 entries but omitted partial-page scope.758 writing clause still stated20 visible vs24 total ambiguously. New hypothesis: explain the distinction in the factual projection itself, without an additional prompt clause or changing original metadata.")
target = root / 'scratchpad/c03-inventory-projection759.py'
assert not target.exists()
target.write_bytes(source.encode('utf-8'))
print(target)
