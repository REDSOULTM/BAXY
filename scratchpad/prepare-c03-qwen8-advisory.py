from pathlib import Path

root = Path(__file__).resolve().parents[1]
old, new = 'qwen2507-mixed-advisory', 'qwen8-mixed-advisory'
out = root / f'artifacts/comprobaciones/C03/astra-{new}'
(out / 'profile').mkdir(parents=True, exist_ok=False)
(out.parent / f'{out.name}.turns.jsonl').write_bytes(
    (out.parent / f'astra-{old}.turns.jsonl').read_bytes())
launcher = (root / f'scratchpad/c03-{old}.py').read_text(encoding='utf-8').replace(old, new)
launcher = launcher.replace(
    'D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf',
    'D:/BAXY/experimental_assets_20260801/Qwen3-8B-Q4_K_M.gguf')
launcher = launcher.replace("'ngl': 99", "'ngl': 20").replace("BAXY_MIND_NGL='99'", "BAXY_MIND_NGL='20'")
launcher = launcher.replace('Qwen3-4B-Instruct-2507#best-practices', 'Qwen3-8B#best-practices')
start = launcher.index("          'hypothesis':")
end = launcher.index("          'profile':", start)
launcher = launcher[:start] + """          'hypothesis': 'Revisit inherited Qwen8 only after the newly demonstrated lexical mixed veto damage: Qwen2507 publishes 12/12 without that veto but still fails useful language/content. Qwen8 previously achieved 10/12 in native composition. Same integrated 12 prompts, advisory-only mixed vocabulary check and all factual/authority guards; no sweep or budget increase.',
          'expected': 'More useful faithful language than the 4B advisory baseline, under total 4096 MiB. Publication alone is not acceptance; adjudicate each response including mixed instructions.',
""" + launcher[end:]
(root / f'scratchpad/c03-{new}.py').write_text(launcher, encoding='utf-8')
profile = (out.parent / f'astra-{old}/profile/sitecustomize.py').read_text(encoding='utf-8')
profile = profile.replace('qwen3-4b-instruct-2507-q4_k_m.gguf', 'qwen3-8b-q4_k_m.gguf')
(out/'profile/sitecustomize.py').write_text(profile, encoding='utf-8')
print(out)
