"""Prepare a product regression after the private configuration parser repair."""
from pathlib import Path
from datetime import datetime, timezone
import ast, json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
original = (root / 'scratchpad/c03-private-product514.py').read_text(encoding='utf-8-sig')
script = original.replace('514', '517')
start = script.index('cases = [')
end = script.index('\n\ncommands', start)
cases = ast.literal_eval(script[start + len('cases = '):end].strip())
cases += ['Desactiva la memoria privada.']
script = script[:start] + 'cases = ' + repr(cases) + script[end:]
start = script.index("    'production_verification':")
end = script.index("    'profile_inheritance':", start)
script = script[:start] + "    'production_verification': '517 actual product: source516 private configuration grammar, source512 mind; registered Qwen/b9980, no treatment. Same nine515 cases in a new isolated profile.',\n    'method': 'Confirm that qualified disable reaches the real private operation and enabled=false is verified. Also check all earlier confirmation, save, recall, conversation and clarification controls. Known result/progress prose failures remain failures; no model ranking or private filtering.',\n" + script[end:]
script = script.replace("['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py','src/baxy_mind/llm.py']", "['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py','src/baxy_mind/llm.py','src/Baxy.App/NaturalMemoryRequestParser.cs']")
target = root / 'scratchpad/c03-private-product517.py'
assert not target.exists()
target.write_text(script, encoding='utf-8')
hook = root / 'scratchpad/c03-owner517-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text((root / 'scratchpad/c03-owner514-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('514', '517'), encoding='utf-8')
out = base / 'astra-product-check517'
out.mkdir(exist_ok=False)
(out / 'PREREG.json').write_text(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases, 'source': 'Source516 must pass owner memory tests and Fast before execution. Only source difference from515 baseline is private memory configuration parsing. No status view filter.', 'criteria': 'T9 actually disables the isolated private memory with enabled=false; never infer disable from prose alone. T1-T8 retain prior binding/confirmation and recall/conversation distinction; internal prose atT2 is still not an acceptable final. Record every visible activity/progress, truthful useful final, resource peak and manifest hash.', 'bounds': 'Same registered runtime, one hidden conductor, new private synthetic profile, no owner memory or physical voice. GPU3800MiB/freeRAM768MiB/240s, owned-tree cleanup. No source edits during run. Not acceptance reserve.'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('517 prepared, not executed; await owners and Fast for516.')
