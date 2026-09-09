from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-polarity52'
out.mkdir(exist_ok=False)
for source, destination in [
    (base / 'astra-progress51.turns.jsonl', out.with_suffix('.turns.jsonl')),
    (base / 'astra-progress51/CASES.json', out / 'CASES.json'),
]:
    destination.write_bytes(source.read_bytes())
driver = (root / 'scratchpad/c03-progress51.py').read_text(encoding='utf-8').replace('progress51', 'polarity52')
start = driver.index("prereg['method'] =")
end = driver.index('\n', start)
method = (
    'Same seven technical inputs, registered runtime and source51 except C# failure-polarity detection. '
    'Negated failure assertions no longer count as failed outcomes; independent affirmative failures '
    'remain visible to the same validator. Native generation, Python progress, catalog and providers unchanged. '
    'The hour/CPU case failed identically in48/49/51 despite faithful drafts because No hay fallos matched '
    'Contains(fallo). New owner tests reproduce both reversal directions and contrast independent failures. '
    'Read-only product conductor; no human reserve, UI or voice claim. Judge whole turns including progress.'
)
driver = driver[:start] + "prereg['method'] = " + repr(method) + driver[end:]
(root / 'scratchpad/c03-polarity52.py').write_text(driver, encoding='utf-8')
print('Prepared seven identical polarity controls.')
