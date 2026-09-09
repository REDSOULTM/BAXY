from pathlib import Path

root = Path(__file__).resolve().parents[1]
old, new = 'qwen8-mixed-advisory', 'qwen8-cpu-budget'
out = root / f'artifacts/comprobaciones/C03/astra-{new}'
(out / 'profile').mkdir(parents=True, exist_ok=False)
(out.parent / f'{out.name}.turns.jsonl').write_bytes(
    (out.parent / f'astra-{old}.turns.jsonl').read_bytes())
launcher = (root / f'scratchpad/c03-{old}.py').read_text(encoding='utf-8').replace(old, new)
launcher = launcher.replace("BAXY_MIND_NGL='20'", "BAXY_MIND_NGL='0'")
start = launcher.index("          'hypothesis':")
end = launcher.index("          'profile':", start)
launcher = launcher[:start] + """          'hypothesis': 'The partial CPU model is killed by GPU-only composition transport deadlines (4s) before its previously measured 6-16s native decode completes. Select existing CPU composition transport budgets in the host; the isolated Python profile sets actual NGL=20 before runtime creation. Same model, prompts, guards and turn-decision budgets; no new deadline constants.',
          'expected': 'Separate inference deadline mismatch from semantic quality. Useful direct output within existing CPU bounds and total GPU below 4096MiB. Record latency honestly; this cannot certify C07.',
""" + launcher[end:]
launcher = launcher.replace("'kv': 'q8_0',", "'kv': 'q8_0', 'hostCompositionBudgetProfile': 'existing CPU; host NGL=0, isolated sidecar NGL=20',")
(root / f'scratchpad/c03-{new}.py').write_text(launcher, encoding='utf-8')
profile = (out.parent / f'astra-{old}/profile/sitecustomize.py').read_text(encoding='utf-8')
profile = profile.replace('from baxy_mind.llm import LlmRuntime', '# Actual partial GPU loading; parent host retains CPU composition deadlines.\nos.environ["BAXY_MIND_NGL"] = "20"\n\nfrom baxy_mind.llm import LlmRuntime')
(out/'profile/sitecustomize.py').write_text(profile, encoding='utf-8')
print(out)
