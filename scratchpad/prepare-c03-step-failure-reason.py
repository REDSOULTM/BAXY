from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
old, new = 'confirmation-route', 'step-failure-reason'
out = root / f'artifacts/comprobaciones/C03/astra-qwen2507-{new}'
(out / 'profile').mkdir(parents=True, exist_ok=False)
turns = [
    {'cmd': 'turn', 'text': 'cierra la calculadora'},
    {'cmd': 'turn', 'text': 'cancelar'},
    {'cmd': 'turn', 'text': '¿Qué hora es?'},
]
(out.parent/f'{out.name}.turns.jsonl').write_text(
    ''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in turns),encoding='utf-8')
launcher = (root/f'scratchpad/c03-qwen2507-{old}.py').read_text(encoding='utf-8').replace(old,new)
launcher = launcher.replace("'src/Baxy.App/MainWindowViewModel.cs',", "'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MissionNarration.cs', 'src/Baxy.App/MindPlanSession.cs',")
start=launcher.index("          'hypothesis':")
end=launcher.index("          'profile':",start)
launcher=launcher[:start]+"""          'hypothesis': 'Reproduce the app.close step failure with original runtime prompts and preserved response.Message plus structured mission reason. No seeded calculator window and no confirmation acceptance: this is a failure-reporting diagnostic.',
          'expected': 'The actual failure cause reaches the composer, no invented successful close, and the session can answer a later clock read. A cancellation acknowledgement alone cannot prove confirmation.',
"""+launcher[end:]
(root/f'scratchpad/c03-qwen2507-{new}.py').write_text(launcher,encoding='utf-8')
(out/'profile/sitecustomize.py').write_bytes(
    (out.parent/f'astra-qwen2507-{old}/profile/sitecustomize.py').read_bytes())
print(out)
