"""Freeze one additional intervention: page instructions after identity projection."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-inventory-projection757.py').read_text(encoding='utf-8-sig')
source = source.replace('757', '758')
source = source.replace('"""Same captured inventory and profile; change only the inventory writing clause."""',
                        '"""Paired identity projections; only the existing754 page instruction changes."""')
source = source.replace("planned = [{'arm': 'captured', 'payload': baseline}, {'arm': 'identity_projection', 'payload': candidate}]", """baseline = copy.deepcopy(candidate)
candidate['messages'][0]['content'] += '\\n' + (
    'For a window list, give each returned window identity concisely: preserve its exact title when present, '
    'otherwise its exact process name. Omit coordinates, dimensions, state, focus and identifiers unless '
    'the person asks for them. State the page count and its scope before the list. '
    'Do not drop returned windows or invent a complete inventory from one page.'
)
assert candidate['messages'][1] == baseline['messages'][1]
planned = [{'arm': 'identity_projection', 'payload': baseline}, {'arm': 'projection_with_page_instruction', 'payload': candidate}]""")
source = source.replace("'change': INSTRUCTION", "'change': 'Same identity projection in both arms; append the unchanged writing clause from754 only to the second system prompt'")
source = source.replace("Projection intervention after instruction-only754-756 did not complete either list.",
                        "757 projection completed20 entries but omitted partial-page scope. This paired probe holds that projection constant and adds the unchanged754 page-writing clause only to the second arm.")
target = root / 'scratchpad/c03-inventory-projection758.py'
assert not target.exists()
target.write_bytes(source.encode('utf-8'))
print(target)
