from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress51'
out.mkdir(exist_ok=False)
for source, destination in [
    (base / 'astra-clock49.turns.jsonl', out.with_suffix('.turns.jsonl')),
    (base / 'astra-clock49/CASES.json', out / 'CASES.json'),
]:
    destination.write_bytes(source.read_bytes())
driver = (root / 'scratchpad/c03-clock49.py').read_text(encoding='utf-8').replace('clock49', 'progress51')
start = driver.index("prereg['method'] =")
end = driver.index('\n', start)
method = (
    'Same seven inputs, registered runtime and source49 except llm progress narration. '
    'Native role51 restored explicit narration responsibility and gave five useful raw replies; '
    'two earlier representation-only variants were rejected. The composer now retains that '
    'instruction in first/retry attempts, without prescribing visible words. Existing instrument '
    'reading/predicate grammar rejects fabricated measurements even alongside a progress marker, '
    'while literal pending numeric targets remain allowed. No changes in C# or provider/model/sampler. '
    'Known C# reversed_result on no-failures prose remains unfixed for isolation. Technical read-only '
    'regression, not human reserve or UI/voice acceptance. Judge the complete visible turn, including labels.'
)
driver = driver[:start] + "prereg['method'] = " + repr(method) + driver[end:]
(root / 'scratchpad/c03-progress51.py').write_text(driver, encoding='utf-8')
print('Prepared seven identical integrated progress controls.')
