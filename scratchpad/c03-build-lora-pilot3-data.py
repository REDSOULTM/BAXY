"""Add missing explicit format supervision while preserving data and runtime contracts."""
from pathlib import Path
import copy
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from baxy_mind.llm import LlmRuntime
OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot3-data'
PARENT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot2-data'
assert not OUT.exists();OUT.mkdir()
class Captured(Exception):pass
class Recorder(LlmRuntime):
    def __init__(self):self._gguf='Qwen3-4B-Instruct-2507-Q4_K_M.gguf';self.payload=None
    def _post(self,payload):self.payload=copy.deepcopy(payload);raise Captured()
def payload(question,lang,history=None):
    recorder=Recorder()
    try:recorder.chat(question,history=history,conversation_kind='knowledge',response_language=lang)
    except Captured:pass
    assert recorder.payload
    return recorder.payload
train=[json.loads(x) for x in (PARENT/'TRAIN.jsonl').read_text(encoding='utf-8').splitlines()]
holdout=[json.loads(x) for x in (PARENT/'HOLDOUT.jsonl').read_text(encoding='utf-8').splitlines()]
# Same eight trained topics; no target answer from evaluation is used.
sentences={
 'evaporation':('La evaporación ocurre cuando un líquido pasa a gas desde su superficie.','Puede suceder sin que el líquido hierva.','Evaporation happens when liquid turns into gas at its surface.','It can happen without the liquid boiling.'),
 'shadow':('Se forma una sombra cuando un objeto bloquea la luz.','La zona situada detrás recibe menos luz.','A shadow forms when an object blocks light.','The area behind it receives less light.'),
 'echo':('Un eco es un sonido que se refleja en una superficie.','Lo escuchas después del sonido original.','An echo is sound reflected from a surface.','You hear it after the original sound.'),
 'fraction':('Una fracción puede representar partes iguales de un todo.','Tres cuartos significa tomar tres de cuatro partes iguales.','A fraction can represent equal parts of a whole.','Three quarters means taking three of four equal parts.'),
 'compass':('Una brújula ayuda a orientarte.','Su aguja señala aproximadamente el norte magnético.','A compass helps you find directions.','Its needle points approximately toward magnetic north.'),
 'bookmark':('Un marcador guarda la dirección de una página para volver a ella.','No guarda necesariamente una copia de su contenido.','A browser bookmark saves a page’s address so you can return to it.','It does not necessarily save a copy of the page itself.'),
 'notification':('Una notificación es un aviso sobre algo que ocurrió o requiere atención.','Puede avisarte de la llegada de un mensaje.','A notification is an alert about an event or something needing attention.','It may tell you that a new message arrived.'),
 'update':('Una actualización puede corregir errores o vulnerabilidades de un programa.','También puede añadir funciones.','A software update can fix bugs or address vulnerabilities.','It can also add features.'),
}
by_id={r['id']:r for r in train}
history=[{'role':'user','content':'What is a triangle?'},{'role':'assistant','content':'A triangle has three straight sides.'},
         {'role':'user','content':'¿Y un cuadrado?'},{'role':'assistant','content':'Tiene cuatro lados iguales y cuatro ángulos rectos.'}]
for topic,(es1,es2,en1,en2) in sentences.items():
    for lang,answer,extra in [('es',es1+' '+es2,' Responde en dos oraciones.'),('en',en1+' '+en2,' Use exactly two sentences.'),
                               ('mixed',es1+' '+en2,' Use two sentences, en spanglish.')]:
        original=by_id[f'knowledge-{topic}-{lang}'];question=original['request']+extra
        train.append({'id':f'format-{topic}-{lang}','language':lang,'request':question,'answer':answer,
                      'payload':payload(question,lang),'synthetic':True,'origin':'Reviewed decomposition of pilot1 training facts; explicit sentence constraint.'})
        train.append({'id':f'format-history-{topic}-{lang}','language':lang,'request':question,'answer':answer,
                      'payload':payload(question,lang,history),'history':history,'synthetic':True,
                      'origin':'Same reviewed training facts with mixed history; final request still owns language and format.'})
reserved=[
 ('perimeter',['¿Qué es el perímetro? Responde en dos oraciones.','What is perimeter? Use two sentences.','What is perimeter? Explícalo en dos oraciones y en spanglish.'], 'Length of the boundary of a shape; may explain adding side lengths for polygons. No invented PC observations.'),
 ('pendulum',['¿Por qué un péndulo termina frenándose? Responde en dos oraciones.','Why does a pendulum eventually slow down? Use two sentences.','Why does a pendulum slow down? Explícalo en dos oraciones y en spanglish.'], 'Air resistance and friction dissipate mechanical energy; no claim that energy disappears.'),
 ('spacing',['¿Para qué sirven los espacios entre palabras? Responde en dos oraciones.','Why put spaces between words? Use two sentences.','Why put spaces between words? Responde en dos oraciones y en spanglish.'], 'Separate words and facilitate reading in languages using word spacing; no universal claim about every writing system.'),
 ('calendar',['¿Para qué sirve un calendario? Responde en dos oraciones.','What is a calendar used for? Use two sentences.','What is a calendar for? Responde en dos oraciones y en spanglish.'], 'Organizes dates/days to locate events or plan; do not claim to read or modify user calendar.'),
]
for topic,questions,criterion in reserved:
    for lang,question in zip(['es','en','mixed'],questions):
        holdout.append({'id':f'format-heldout-{topic}-{lang}','language':lang,'request':question,
                        'payload':payload(question,lang,history),'criteria':criterion+' Exactly two sentences; requested language; no full translation repetition.',
                        'synthetic':True,'history':history})
assert len(train)==132 and len(holdout)==30
assert not ({r['request'] for r in train}&{r['request'] for r in holdout})
for name,rows in [('TRAIN.jsonl',train),('HOLDOUT.jsonl',holdout)]:
    (OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
manifest={'kind':'development-format-coverage-pilot-not-acceptance','trainCount':132,'holdoutCount':30,
 'hypothesis':'All 28 prior mixed-language training targets have one sentence and no explicit sentence-count request. Add 48 examples following two-sentence requests, including mixed history, without changing model, loss, hyperparameters, or holdout answers.',
 'inheritance':'Reuse all 84 reviewed pilot2 examples, their input construction and response-only training inherited from the Gemma project. Historical train_v3 is not bulk inherited: inspected examples contain identity substitution and obsolete privacy rules.',
 'criterion':'Compare same 27 prior cases and 12 new frozen format holdouts with v2. Read each answer; format gains must not trade away facts, language or usefulness. No scale sweep.',
 'files':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['TRAIN.jsonl','HOLDOUT.jsonl']}}
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
runner=(ROOT/'scratchpad/c03-train-lora-pilot.py').read_text(encoding='utf-8').replace('48-example','132-example').replace('astra-lora-pilot-training','astra-lora-pilot3-training').replace('c03-pilot-lora-v1','c03-pilot-lora-v3').replace('astra-lora-pilot-data','astra-lora-pilot3-data')
target=ROOT/'scratchpad/c03-train-lora-pilot3.py';assert not target.exists();target.write_text(runner,encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
