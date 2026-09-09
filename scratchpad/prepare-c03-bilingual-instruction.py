from pathlib import Path

root = Path(__file__).resolve().parents[1]
old, new = 'code-switch', 'bilingual-instruction'
out = root / f'artifacts/comprobaciones/C03/astra-qwen2507-{new}'
(out / 'profile').mkdir(parents=True, exist_ok=False)
turns = root / f'artifacts/comprobaciones/C03/astra-qwen2507-{old}.turns.jsonl'
(out.parent / f'{out.name}.turns.jsonl').write_bytes(turns.read_bytes())
launcher = (root / f'scratchpad/c03-qwen2507-{old}.py').read_text(encoding='utf-8')
launcher = launcher.replace(old, new)
start = launcher.index("          'hypothesis':")
end = launcher.index("          'profile':", start)
launcher = launcher[:start] + """          'hypothesis': 'Use a bilingual instruction that demonstrates ordinary switching, without demanding a full clause in each language. Source includes independently tested clock-unit equivalence and language-wrapper repair. This is the last wording diagnostic; not isolated attribution for those source repairs.',
          'expected': 'Direct useful mixed answers without duplicate translations, invented effects or exhausted composition. Guards and total budgets retained. No promotion.',
""" + launcher[end:]
launcher = launcher.replace("'src/baxy_mind/request_reading.py',", "'src/baxy_mind/request_reading.py', 'src/baxy_mind/effect_intent.py', 'src/Baxy.App/PendingModelMessageQueue.cs',")
launcher = launcher.replace("BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'))", "BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'),\n           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out/'raw-replies.jsonl'))")
(root / f'scratchpad/c03-qwen2507-{new}.py').write_text(launcher, encoding='utf-8')
profile = (out.parent / f'astra-qwen2507-{old}/profile/sitecustomize.py').read_text(encoding='utf-8')
start = profile.index('_new_language_instruction = (')
end = profile.index('\n\n\ndef _code_switch_post', start)
profile = profile[:start] + """_new_language_instruction = (
    "Responde en spanglish with natural switches between Spanish and English. "
    "Cada parte debe aportar información, so don't translate your whole answer twice. "
    "Mantén el contenido útil and answer the actual question directly."
)
""" + profile[end:]
(out / 'profile/sitecustomize.py').write_text(profile, encoding='utf-8')
print(out)
