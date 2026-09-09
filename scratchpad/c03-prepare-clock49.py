from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-clock49'
out.mkdir(exist_ok=False)
for source, destination in [
    (base / 'astra-compound-shell48.turns.jsonl', out.with_suffix('.turns.jsonl')),
    (base / 'astra-compound-shell48/CASES.json', out / 'CASES.json'),
]:
    destination.write_bytes(source.read_bytes())
driver = (root / 'scratchpad/c03-compound-shell48.py').read_text(encoding='utf-8')
driver = driver.replace('compound-shell48', 'clock49')
method = (
    'Same seven inputs and registered runtime as compound-shell48. Only source difference '
    'is effect_intent clause normalization: retain shared clock/audio observations and '
    'coordinated state questions, preserving ordering and catalog completeness. '
    'No new clock/audio classifier or fixed plan; no model/prompt/sampler change. '
    'Known progress hallucination and false failure-polarity rejection remain unfixed '
    'in this comparison. Do not count a faithful final as a pass when progress is false. '
    'Technical read-only panel, not human reserve or UI/voice acceptance.'
)
start = driver.index("prereg['method'] =")
end = driver.index('\n', start)
driver = driver[:start] + "prereg['method'] = " + repr(method) + driver[end:]
(root / 'scratchpad/c03-clock49.py').write_text(driver, encoding='utf-8')
print(json.dumps({'prepared': str(out), 'inputsIdenticalTo48': True}))
