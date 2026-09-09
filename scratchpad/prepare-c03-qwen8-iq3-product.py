from pathlib import Path

root = Path(__file__).resolve().parents[1]
old, new = 'qwen8-cpu-budget', 'qwen8-iq3-product'
out = root/f'artifacts/comprobaciones/C03/astra-{new}'
(out/'profile').mkdir(parents=True, exist_ok=False)
(out.parent/f'{out.name}.turns.jsonl').write_bytes(
    (out.parent/f'astra-{old}.turns.jsonl').read_bytes())
launcher = (root/f'scratchpad/c03-{old}.py').read_text(encoding='utf-8').replace(old,new)
launcher = launcher.replace('D:/BAXY/experimental_assets_20260801/Qwen3-8B-Q4_K_M.gguf',
    'D:/BAXYRuntime/experiments/models/qwen3-8b-iq3-xxs-0b69f75b/Qwen_Qwen3-8B-IQ3_XXS.gguf')
launcher = launcher.replace("BAXY_MIND_NGL='0'", "BAXY_MIND_NGL='30'")
launcher = launcher.replace("BAXY_MIND_KV_CACHE_TYPE='q8_0'", "BAXY_MIND_KV_CACHE_TYPE='q4_0'")
launcher = launcher.replace("'ngl': 20", "'ngl': 30")
launcher = launcher.replace("'kv': 'q8_0', 'hostCompositionBudgetProfile': 'existing CPU; host NGL=0, isolated sidecar NGL=20',",
    "'kv': 'q4_0', 'hostCompositionBudgetProfile': 'unchanged GPU 5/10s',")
launcher = launcher.replace("sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()", '''def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()''')
start=launcher.index("          'hypothesis':")
end=launcher.index("          'profile':",start)
launcher=launcher[:start]+"""          'hypothesis': 'One preregistered smaller quant of inherited Qwen8, IQ3_XXS, with ngl30 and q4_0 KV reduces CPU work while staying under total4096MiB. The Q4 CPU-budget comparison recovered publications but still timed out during interpretation. Same 12 development prompts and current product guards; no enlarged deadlines, prompt changes or quant sweep.',
          'expected': 'More useful faithful ES/EN/mixed output than the Qwen2507 advisory baseline (at most8/12), with zero GPU ceiling breach. Publication counts alone do not pass. No model promotion; reject this one candidate if it fails.',
"""+launcher[end:]
(root/f'scratchpad/c03-{new}.py').write_text(launcher,encoding='utf-8')
profile=(out.parent/f'astra-{old}/profile/sitecustomize.py').read_text(encoding='utf-8')
profile=profile.replace('# Actual partial GPU loading; parent host retains CPU composition deadlines.\nos.environ["BAXY_MIND_NGL"] = "20"\n\n','')
profile=profile.replace('qwen3-8b-q4_k_m.gguf','qwen_qwen3-8b-iq3_xxs.gguf')
(out/'profile/sitecustomize.py').write_text(profile,encoding='utf-8')
print(out)
