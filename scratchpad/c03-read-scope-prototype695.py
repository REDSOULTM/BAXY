"""Isolated next-candidate probe while Full693 runs; never edit its source."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import re
import sys
import types

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
import baxy_mind.effect_intent as baseline
path=root/'src/baxy_mind/effect_intent.py'
original=path.read_text(encoding='utf-8')
source=original
start=source.index('def _direct_current_time_request(')
end=source.index('\ndef _direct_media_discovery_or_play_request',start)
chunk=source[start:end]
old='    return (\n'
assert chunk.count(old)==1
extra=r'''    observation = re.fullmatch(
        r"(?:(?:dime|decime|dame|muestra|muestrame|mostrame|pasame|tirame)\s+"
        r"(?:(?:la|el)\s+)?(?:hora|fecha)(?:\s+(?:local|actual|de\s+hoy))?|"
        r"(?:what\s+is|what's|tell\s+me|show\s+me|give\s+me)\s+"
        r"(?:the\s+)?(?:current\s+)?(?:local\s+)?(?:time|date)"
        r"(?:\s+(?:right\s+now|now|today))?)"
        r"(?:\s+(?:por\s+favor|please))?[\s.!?]*",
        folded.lstrip("¿¡ "), re.IGNORECASE,
    )
    return observation is not None or (
'''
chunk=chunk.replace(old,extra)
source=source[:start]+chunk+source[end:]
old=r'r"\b(?:un|una|a|an|otro|otra|another)\s+(?:\w+\s+){0,2}"'
new=r'r"\b(?:un|una|a(?!\s+(?:la|el|mi|esta|este)\b)|an|otro|otra|another)\s+(?:\w+\s+){0,2}"'
assert source.count(old)==1
source=source.replace(old,new)
for name,next_name in [('_STATE_QUERY_HEAD','_MACHINE_STATUS_HEAD'),('_MACHINE_STATUS_HEAD','_MACHINE_STATUS_OBSERVATION'),('_MACHINE_STATUS_OBSERVATION_HEAD','def _is_direct_request')]:
    start=source.index(name+' = (');end=source.index(next_name,start+len(name))
    chunk=source[start:end]
    assert chunk.count('dame|')==1
    source=source[:start]+chunk.replace('dame|','dame|tirame|')+source[end:]
helper=r'''
def _fronted_machine_observation(text: str) -> str:
    """Move a delimited physical topic after its observation request."""
    match = re.fullmatch(
        r"(?P<frame>(?:de|del|sobre|regarding|about|for|as\s+for)\s+"
        r"(?P<topic>[^,;:.!?]{1,64}))\s*[,;:]\s*"
        r"(?P<request>(?:dime|decime|dame|muestra|muestrame|mostrame|"
        r"tell\s+me|show\s+me|give\s+me)\s+.+)", text,
    )
    if match is None:
        return text
    topic = match['topic']
    if not _system_status_domain(topic) and not _volume_domain(topic):
        return text
    return match['request'] + ' ' + match['frame']

'''
source=source.replace('\ndef resolve_explicit_effects(',helper+'\ndef resolve_explicit_effects(',1)
needle='    folded = _strip_request_envelope(_fold(re.sub(r"[\\r\\n]+", " . ", text)))\n'
start=source.index('def resolve_explicit_effects(')
assert needle in source[start:]
source=source[:start]+source[start:].replace(needle,needle+'    folded = _fronted_machine_observation(folded)\n',1)
module=types.ModuleType('baxy_mind._read_scope_candidate695')
module.__package__='baxy_mind'
module.__file__=str(path)
sys.modules[module.__name__]=module
exec(compile(source,str(path),'exec'),module.__dict__)
catalog=(root/'src/Baxy.Kernel/Operations/ProductCatalog.cs').read_text(encoding='utf-8')
operations=frozenset(re.findall(r'Descriptor\(\s*"([a-z][a-z0-9_.]+)"',catalog))
home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
registry=home/'C03-survey-requirements336-private/requirements.jsonl'
requirements=[json.loads(line) for line in registry.read_text(encoding='utf-8-sig').splitlines()]
out=home/'C03-read-scope-prototype695-private'
out.mkdir(exist_ok=False)
def resolved(mod,text):
    answer=mod.resolve_explicit_effects(text,operations)
    return list(answer.operations) if answer is not None else []
changes=[]
for row in requirements:
    old,new=resolved(baseline,row['literal']),resolved(module,row['literal'])
    if old!=new:changes.append({'case_id':row['case_id'],'text':row['literal'],'before':old,'after':new,'owner_review':row['owner_review']})
panel=json.loads((home/'C03-status-batch689-private/panel.json').read_text(encoding='utf-8'))
batch=[{'case_id':r['case_id'],'text':r['text'],'before':resolved(baseline,r['text']),'after':resolved(module,r['text'])} for r in panel]
negative=[
 'No me muestres la hora.', 'Mostrame la hora de Tokio.', 'Mostrame la fecha de mi cumpleaños.',
 'What is a local date?', 'What is the date format?', 'Tell me the date of the next eclipse.',
 'Tirame un archivo a la papelera.', 'Tirame cuánta RAM debería comprar.',
 'Cuánta batería le queda a otra notebook', 'Cuánta batería necesita una notebook',
 'How much battery does a laptop need?', 'De la CPU, borra sus archivos.',
 'Del disco C, dime cuánto espacio había ayer.', 'For the CPU, tell me why it is hot.',
 'Sobre mi teléfono, dime la batería restante.', 'About a book, tell me the volume.',
 'Escribe "mostrame la hora" en una nota.', 'Dile a Ana "mostrame la fecha".',
]
controls=[{'text':text,'before':resolved(baseline,text),'after':resolved(module,text)} for text in negative]
result={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'survey_rows':742,
 'method':'Isolated in-memory module against all742 original literals and frozen73 batch. No model, provider or source edit. Changes are proposed operation lists, not correctness or coverage.',
 'survey_changes':changes,'batch':batch,'negative_controls':controls,'adopted':False}
(out/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'candidate.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='a/src/baxy_mind/effect_intent.py',tofile='b/src/baxy_mind/effect_intent.py')),encoding='utf-8')
assert path.read_text(encoding='utf-8')==original
print(json.dumps({'survey_changes':[{k:r[k] for k in ['case_id','before','after']} for r in changes],
 'batch_changes':[{k:r[k] for k in ['case_id','before','after']} for r in batch if r['before']!=r['after']],
 'negative_changes':[r for r in controls if r['before']!=r['after']],'source_modified':False},ensure_ascii=False))
