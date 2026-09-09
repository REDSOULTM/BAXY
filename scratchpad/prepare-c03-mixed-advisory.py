from pathlib import Path

root = Path(__file__).resolve().parents[1]
old, new = 'bilingual-instruction', 'mixed-advisory'
out = root / f'artifacts/comprobaciones/C03/astra-qwen2507-{new}'
(out / 'profile').mkdir(parents=True, exist_ok=False)
turns = out.parent / f'astra-qwen2507-{old}.turns.jsonl'
(out.parent / f'{out.name}.turns.jsonl').write_bytes(turns.read_bytes())
launcher = (root / f'scratchpad/c03-qwen2507-{old}.py').read_text(encoding='utf-8').replace(old, new)
start = launcher.index("          'hypothesis':")
end = launcher.index("          'profile':", start)
launcher = launcher[:start] + """          'hypothesis': 'Measure publication without the positive bilingual vocabulary veto. Original product prompts and all factual, authority, echo and structural checks retained; log every would-be language veto. Human adjudication remains strict and independent of publication count.',
          'expected': 'Less retry damage and useful answers preserved; language quality judged from actual outputs, not a forced green validator. Development only, no promotion.',
""" + launcher[end:]
(root / f'scratchpad/c03-qwen2507-{new}.py').write_text(launcher, encoding='utf-8')
base = (out.parent / 'astra-qwen2507-code-switch/profile/sitecustomize.py').read_text(encoding='utf-8')
base = base[:base.index('# Diagnostic-only: replace')]
base += '''# Diagnostic-only: preserve the would-be veto in the existing capture.
from baxy_mind import llm as llm_module

_mixed_veto = llm_module._reply_drops_mixed_language


def _audit_mixed_style(text, language):
    flagged = _mixed_veto(text, language)
    if flagged:
        with _audit.with_name("language-advisory.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"language": language, "text": text, "wouldReject": True}, ensure_ascii=False) + "\\n")
    return False


llm_module._reply_drops_mixed_language = _audit_mixed_style
'''
(out / 'profile/sitecustomize.py').write_text(base, encoding='utf-8')
print(out)
