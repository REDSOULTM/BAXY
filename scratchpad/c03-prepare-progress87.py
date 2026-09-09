from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-phase85.py').read_text(encoding='utf-8')
source = source.replace("'astra-progress-phase85'", "'astra-progress-activity87'")
source = source.replace("for variant in ('captured', 'understanding'):", "for variant in ('request_interpretation',):")
source = source.replace("if variant == 'understanding':", "if variant == 'request_interpretation':")
source = source.replace("situation['phase'] = 'understanding'", "situation['state'] = \"understanding the person's request\"")
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Native prototype: same six packets82 and sampler/model; replace only state=in progress '
    'with state=understanding the person\\'s request. Baseline82 and phase-only85 already captured; no need to '
    'repeat identical baselines again. The vague phase85 did not improve the why question or file cases; '
    'this tests the semantic activity instead of appending a phase label. No extra instruction or source change. '
    'Known-understanding fixture phase assumed, not actual effect execution or publication. No UI/audio/reserve/promotion.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-activity87.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
