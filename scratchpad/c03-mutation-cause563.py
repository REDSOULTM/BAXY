"""Remove the duplicate generated cause from the coherent receipt562."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-mutation-view562.py').read_text(encoding='utf-8')
source=source.replace('astra-mutation-view562','astra-mutation-cause563').replace('C03-mutation-view562-private','C03-mutation-cause563-private')
# This is source inside562's replacement string; preserve its newline escape.
source=source.replace("facts['seen']['label']=selector\\n            facts['seen']", "facts['seen']['label']=selector\\n            facts.pop('state',None)\\n            facts['seen']")
source=source.replace('Keep saved:true, all true states, original prompt, request and outcome.', 'Keep saved:true, all true receipt flags, original prompt, request and outcome; omit only duplicate state:memory updated, derived from C# cause memory_updated.562 removed unsupported false-state claims but the generated cause was still recited after the target. This isolates that redundant cause cue from the same coherent receipt.')
exec(compile(source,__file__,'exec'))
