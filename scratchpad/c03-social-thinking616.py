"""Compare direct and thinking guard outputs under Gemma's documented profile."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-social-kind615.py').read_text(encoding='utf-8')
source = source.replace('astra-social-kind615', 'astra-social-thinking616')
source = source.replace('C03-social-kind615-private', 'C03-social-thinking616-private')
start = source.index('panel=[]')
end = source.index("write(private/'panel.json',panel)", start)
source = source[:start] + '''panel=[]
for case_id,text,expected,count in cases:
    for thinking in [False, True]:
        payload=copy.deepcopy(candidate)
        payload['messages'][-1]['content']='Mensaje actual:\\n'+text
        payload.update(temperature=1.0,top_p=.95,top_k=64,min_p=0.0,
                       presence_penalty=0.0,repeat_penalty=1.0,
                       max_tokens=3072,reasoning_budget_tokens=-1,verbose=True)
        payload['chat_template_kwargs']={'enable_thinking':thinking}
        panel.append({'case_id':case_id,'text':text,
                      'arm':'thinking' if thinking else 'direct',
                      'expected_type':expected,'expected_count':count,'payload':payload})
''' + source[end:]
source = source.replace("command=json.loads((prior/'effective-server-command.json').read_text(encoding='utf-8'))",
                        "command=json.loads((private.parent/'C03-gemma-original497-private/effective-server-command.json').read_text(encoding='utf-8'))")
start = source.index("    'hypothesis':")
end = source.index("    'command':", start)
source = source[:start] + '''    'hypothesis':'615 social subtype identifies social reactions but mislabels identity/drafted content and a named-source read. Reject source adoption. Determine whether native Gemma reasoning can distinguish all declared classes before considering a runtime representation change.',
    'method':'Same20 frozen615 cases and candidate prompt/grammar. Documented Google T1/p.95/k64/min0, presence0/repeat1,3072 tokens for both direct and thinking. Only enable_thinking differs between these two arms. Relative to615 this is a profile comparison, not a claim isolating a single sampler change. Capture actual thoughts, finish reasons, raw labels and normalized no-effect counts. No source/registry changes or response rewriting.',
    'criteria':'Require correct type/count across the entire20-case panel, retain all failures and thought/cut costs. Social labels must not erase an informational request; incorrect raw stable counts are recorded separately from runtime normalization. Success is not product qualification or survey coverage. After this second bounded representation/profile attempt, if no viable general distinction emerges, abandon this classifier route rather than iterate prompt variants.',
    'research_reused':['https://ai.google.dev/gemma/docs/capabilities/thinking','https://huggingface.co/google/gemma-4-E2B-it/blob/main/generation_config.json'],
''' + source[end:]
source = source.replace("'seconds':240", "'seconds':360")
source = source.replace("tail=tail.replace('Collected40", "tail=tail.replace('> 240', '> 360').replace('urlopen(request,timeout=30)', 'urlopen(request,timeout=90)')\ntail=tail.replace('Collected40")
source = source.replace('Collected40 native social-subtype classifications', 'Collected40 native direct/thinking classifications')
exec(compile(source, __file__, 'exec'))
