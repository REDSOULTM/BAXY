from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-topic-context47'
out.mkdir(exist_ok=False)
commands = (base / 'astra-wire-context47.turns.jsonl').read_text(encoding='utf-8').splitlines()[:10]
out.with_suffix('.turns.jsonl').write_text('\n'.join(commands) + '\n', encoding='utf-8')
(out / 'CASES.json').write_text(json.dumps({'kind': 'same consumed technical prefix10',
    'candidate': 'Existing new-topic mechanism recognizes a terminal simple-language modifier; no prompt/model/history-storage changes.',
    'notAcceptance': True}, indent=2), encoding='utf-8')
driver = (root / 'scratchpad/c03-wire-context47.py').read_text(encoding='utf-8').replace('wire-context47', 'topic-context47')
method = ('Same10 consumed technical prefix and order as wire-context47. Registered model/backend/sampler unchanged; '
          'same opt-in exact-payload logging hook. Only request_reading terminal style modifier changes. '
          'Tests preserve existing subjects, reference-dependent explanations and caller history. '
          'The raw failed-panel reconstruction reproduced the Moon phrase with the identical captured policies; '
          'no-context control removed it. Product run checks that this conditional scope reaches the real generation. '
          'Not acceptance, not UI/audio, not repeat-until-green. Known CPU omission and literal-path resolution failures '
          'remain separately recorded and are not retried in this prefix.')
driver = '\n'.join(f"prereg['method'] = {method!r}" if line.startswith("prereg['method'] =") else line
                   for line in driver.splitlines()) + '\n'
(root / 'scratchpad/c03-topic-context47.py').write_text(driver, encoding='utf-8')
print('Prepared corrected-source prefix10 with exact-payload hook.')
