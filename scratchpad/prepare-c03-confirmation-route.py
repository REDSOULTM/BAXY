from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
old, new = 'bilingual-instruction', 'confirmation-route'
out = root / f'artifacts/comprobaciones/C03/astra-qwen2507-{new}'
(out / 'profile').mkdir(parents=True, exist_ok=False)
turns = [
    {'cmd': 'turn', 'text': 'abre la calculadora'},
    {'cmd': 'turn', 'text': 'cierra la calculadora'},
    {'cmd': 'turn', 'text': 'cancelar'},
    {'cmd': 'turn', 'text': '¿Qué hora es?'},
    {'cmd': 'session.new'},
    {'cmd': 'turn', 'text': 'close the calculator'},
    {'cmd': 'turn', 'text': 'cancel'},
    {'cmd': 'turn', 'text': 'Tell me the time and the volume.'},
    {'cmd': 'turn', 'text': 'no abras Paint'},
]
(out.parent / f'{out.name}.turns.jsonl').write_text(
    ''.join(json.dumps(t, ensure_ascii=False) + '\n' for t in turns), encoding='utf-8')
launcher = (root / f'scratchpad/c03-qwen2507-{old}.py').read_text(encoding='utf-8').replace(old, new)
start = launcher.index("          'hypothesis':")
end = launcher.index("          'profile':", start)
launcher = launcher[:start] + """          'hypothesis': 'Exercise real app.close confirmation (WorkLoss/Sensitive in the catalog) after opening Calculator. Cancel instead of confirming in ES and EN; read-only queries verify continuation. No request to send external messages or power off. Original product guards/prompts.',
          'expected': 'Verified calculator open, exact close confirmation in the requested language, honest cancellation and useful subsequent queries. Record effects rather than infer confirmation from a cancel acknowledgement.',
""" + launcher[end:]
(root / f'scratchpad/c03-qwen2507-{new}.py').write_text(launcher, encoding='utf-8')
profile = (out.parent / 'astra-qwen2507-code-switch/profile/sitecustomize.py').read_text(encoding='utf-8')
profile = profile[:profile.index('# Diagnostic-only: replace')]
(out/'profile/sitecustomize.py').write_text(profile, encoding='utf-8')
print(out)
