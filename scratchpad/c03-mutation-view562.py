"""Test the interaction of two identified losses in the mutation receipt view."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-mutation-target539.py').read_text(encoding='utf-8')
source=source.replace('astra-mutation-target539','astra-mutation-view562').replace('C03-mutation-target539-private','C03-mutation-view562-private')
source=source.replace("facts['seen']['label']=selector", "facts['seen']['label']=selector\n            facts['seen']={key:value for key,value in facts['seen'].items() if not (key in {'corrected','sensitive','replayed'} and value is False)}")
source=source.replace('Add seen.label using that selector, keep every existing flag, original prompt, shape and request.', 'Combine target preservation with omission of only false corrected/sensitive/replayed bookkeeping fields from the public view. Keep saved:true, all true states, original prompt, request and outcome. This tests the interaction, not a claim that either change alone worked.')
source=source.replace('515 removed false flags without target grounding and failed; this keeps those flags and tests only lost target.', '515 omitted false flags without the lost target and failed;539 restored the target with all flags and still recited bookkeeping. These independent failures leave the interaction untested. Test one coherent public receipt projection before changing source; after this bounded comparison, do not keep sweeping receipt wording.')
exec(compile(source,__file__,'exec'))
