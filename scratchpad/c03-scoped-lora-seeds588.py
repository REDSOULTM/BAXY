"""Check scoped adapter beyond one seed, including completed CPU missions."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-scoped-lora586.py').read_text(encoding='utf-8')
source = source.replace('astra-scoped-lora586', 'astra-scoped-lora-seeds588').replace('C03-scoped-lora586-private', 'C03-scoped-lora-seeds588-private')
needle = 'assert len(cases)==15'
source = source.replace(needle, needle + '''
recent=[json.loads(s) for s in (private.parent/'C03-cpu-actor-product582-private/http-posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
cases += [{'id':r['id'],'case':'582:'+str(r['id']),'payload':r['payload'],'cpu_scope':True} for r in recent if r['stage']=='request' and r['id'] in (1,3,5,7)]
assert len(cases)==19
''')
start = source.index("profiles=[('registered-base'"); end = source.index("write(out/'PREREG.json'", start)
source = source[:start] + "profiles=[('scoped-pilot4-seed17',{**documented,'seed':17,'lora':[{'id':0,'scale':1.}]}),('scoped-pilot4-seed42',{**documented,'seed':42,'lora':[{'id':0,'scale':1.}]})]\n" + source[end:]
source = source.replace('Eight exact recent CPU writer inputs582, four new synthetic CPU fixtures varying request, values, core ratios and processor label; three inherited name/confirmation controls following CPU requests. Registered base, documented sampling base, identical sampling plus inherited pilot4 only on CPU inputs.', 'Inherit all fifteen586 cases and append four actual CPU model/count writers582, including completed missions with ordered reads. Same scoped adapter and documented sampling, new seeds17/42. No rerun of seed0 or baseline; this checks variability and mission generalization before integration.')
source = source.replace('45 scoped adapter writer requests collected', '38 scoped adapter seed writer requests collected')
source = source.replace("source = source.replace('if gpu.peak_mib>3800:'", "source = source.replace('case_index%3', 'case_index%2')\nsource = source.replace('if gpu.peak_mib>3800:'")
exec(compile(source, __file__, 'exec'))
