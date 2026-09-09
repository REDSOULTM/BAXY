"""Isolate the save request lost when the current turn is only confirmation."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-mutation-target539.py').read_text(encoding='utf-8')
source=source.replace('astra-mutation-target539','astra-bound-save-request564').replace('C03-mutation-target539-private','C03-bound-save-request564-private')
start=source.index('def treatment(payload,selector):')
end=source.index("write(out/'PREREG.json'",start)
source=source[:start]+'''def treatment(payload,selector):
    requests={'name':'My name is Jordan. Remember my name.',
              'favorite color':'My favorite color is orange. Remember it.',
              'pet name':'My pet is called Nori. Remember that name.',
              'delivery preference':'Remember that I prefer deliveries in the afternoon.'}
    lines=payload['messages'][1]['content'].splitlines()
    assert lines[0]=='confirm'
    lines[0]=requests[selector]
    payload['messages'][1]['content']='\\\\n'.join(lines)
''' +source[end:]
source=source.replace('Add seen.label using that selector, keep every existing flag, original prompt, shape and request.', 'Replace only the current confirmation word with the original bound save request; do not add selector or remove flags/cause. Name/Jordan inherits the actual521 initial request; the other three are explicitly counterfactual save requests, not real effects.')
source=source.replace('515 removed false flags without target grounding and failed; this keeps those flags and tests only lost target.', '539 target alone failed;562/563 reduced false-flag and cause recital but the name receipt remains mechanical. Current compose receives only confirm even for resumed saved request. Test this context loss rather than more field renaming; no source adoption unless correspondence to the exact prepared invocation can be preserved safely.')
exec(compile(source,__file__,'exec'))
