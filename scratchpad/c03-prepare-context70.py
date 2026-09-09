from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-selector-context69.py').read_text(encoding='utf-8')
target = root / 'scratchpad/c03-selector-context70.py'
assert not target.exists()
source = source.replace('astra-selector-context69', 'astra-selector-context70')
source = source.replace('        client.begin_request(40)', "        dependency.pop('response_format')\n        client.begin_request(40)", 1)
source = source.replace("'contextPrompt': prompt,", "'difference70': 'Remove only response_format from the context-dependence request. Preserve the entire69 instruction, literal input, seed, temperature and32-token limit. No production change; distinguish format-induced boolean collapse from semantic inability.',\n          'contextPrompt': prompt,", 1)
target.write_text(source, encoding='utf-8')
print('prepared70')
