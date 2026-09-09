"""Qualify a finite thinking budget; never promote from this native diagnostic."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-qwen9b-thinking567.py').read_text(encoding='utf-8')
source = source.replace('astra-qwen9b-thinking567', 'astra-qwen9b-bounded583').replace('C03-qwen9b-thinking567-private', 'C03-qwen9b-bounded583-private')
source = source.replace("assert len(cases)==12", """assert len(cases)==12
recent=[json.loads(s) for s in (private.parent/'C03-cpu-actor-product582-private/http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
cases += [{'id':r['id'],'case':'582:'+str(r['id']),'payload':r['payload']} for r in recent if r['stage']=='request' and r['id'] in (7,10,12,20)]
assert len(cases)==16""")
source = source.replace("('--reasoning-budget','-1')", "('--reasoning-budget','256')")
source = source.replace("'documented-thinking-seed0'", "'documented-thinking-budget256-seed0'")
source = source.replace("'max_tokens':6144,'reasoning_budget_tokens':-1", "'max_tokens':768,'thinking_budget_tokens':256")
source = source.replace('Twelve unchanged current writer captures557/566', 'Twelve inherited writer captures557/566 plus four current initial CPU writers582')
source = source.replace('No intermediate cutoff;6144 total output tokens within8192 context for these short prompts.', 'Finite256 reasoning tokens at the command line and768 total output tokens. This changes the unlimited567 budget, not prompts, observations, sampler or model. Inspect actual forcing logs and finals; a truncated final remains a failure.')
source = source.replace("'https://github.com/ggml-org/llama.cpp/pull/28068'", "'https://github.com/ggml-org/llama.cpp/pull/28068','https://github.com/ggml-org/llama.cpp/discussions/21445'")
source = source.replace('12 reasoning writer requests collected', '16 bounded reasoning writer requests collected')
exec(compile(source, __file__, 'exec'))
