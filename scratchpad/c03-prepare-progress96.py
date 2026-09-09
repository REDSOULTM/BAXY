from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-activity87.py').read_text(encoding='utf-8')
source = source.replace("'astra-progress-activity87'", "'astra-progress-state96'")
source = source.replace("cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]",
    "cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()][:2]")
source = source.replace("for variant in ('request_interpretation',):", "for variant in ('state_only',):")
source = source.replace("if variant == 'request_interpretation':", "if variant == 'state_only':")
source = source.replace("payload['messages'][-1]['content'] = '\\n'.join(lines)",
    "payload['messages'][-1]['content'] = '\\n'.join(line for line in lines if not line.startswith('Texto original de la persona: '))")
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'State-authority scoping prototype after raw-request framing/profile failures. Exact87 factual '
    'state, original system progress instruction, greedy non-thinking model/profile. Remove only original '
    'request text from the narrator packet while the known phase is understanding. Language and factual '
    'activity remain. The request is still the planner input; this is only progress composition. '
    'Only two distinct packets remain, English and Spanish; do not count four redundant erased-request '
    'cases as independent evidence. Evaluate truthful natural activity without invented effects or outcomes. '
    'No fixed visible text, source change, UI/audio/reserve or promotion. Native phase assumed, not observed.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-state96.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
