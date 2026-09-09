"""Small synthetic development-only SFT set and frozen disjoint diagnostic holdout."""
from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from baxy_mind.llm import LlmRuntime

OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot-data'
assert not OUT.exists()
OUT.mkdir()
class Captured(Exception):
    pass
class Recorder(LlmRuntime):
    def __init__(self):
        self._gguf='Qwen3-4B-Instruct-2507-Q4_K_M.gguf';self.payload=None
    def _post(self,payload):
        self.payload=copy.deepcopy(payload);raise Captured()

def capture(question,language,situation=None):
    recorder=Recorder()
    try:
        if situation is None:
            recorder.chat(question,history=[],conversation_kind='knowledge',response_language=language)
        else:
            recorder.compose_user_message(question,'status',{'situation':json.dumps(situation)})
    except Captured:
        pass
    assert recorder.payload
    return recorder.payload

# Each topic has one ES, EN and mixed example. None is a reserved acceptance case.
topics=[
 ('evaporation',
  ['¿Qué es la evaporación?','What is evaporation?','Explain evaporation, pero en simple.'],
  ['La evaporación ocurre cuando un líquido pasa a gas desde su superficie. Puede suceder sin que el líquido hierva.',
   'Evaporation happens when liquid turns into gas at its surface. It can happen without the liquid boiling.',
   'La evaporación es el paso de un líquido a gas desde su superficie; it can happen even when the liquid is not boiling.']),
 ('shadow',
  ['¿Por qué se forma una sombra?','Why does a shadow form?','¿Por qué aparece una sombra? Answer in Spanglish.'],
  ['Se forma una sombra cuando un objeto bloquea la luz. La zona situada detrás recibe menos luz.',
   'A shadow forms when an object blocks light. The area behind it receives less light.',
   'Una sombra aparece cuando un objeto bloquea la luz; the area behind it receives less light.']),
 ('echo',
  ['¿Qué es un eco?','What is an echo?','Explain an echo, sin tecnicismos.'],
  ['Un eco es un sonido que se refleja en una superficie y vuelve a escucharse después del original.',
   'An echo is sound reflected from a surface and heard again after the original sound.',
   'Un eco es un sonido que rebota en una superficie; you hear it again after the original sound.']),
 ('fraction',
  ['¿Qué representa una fracción?','What does a fraction represent?','¿Qué representa una fracción? Reply in Spanglish.'],
  ['Una fracción puede representar partes iguales de un todo. En tres cuartos, el todo se divide en cuatro partes iguales y se toman tres.',
   'A fraction can represent equal parts of a whole. Three quarters means the whole is divided into four equal parts and three are taken.',
   'Una fracción puede representar partes iguales de un todo; three quarters means taking three of four equal parts.']),
 ('compass',
  ['¿Para qué sirve una brújula?','What is a compass used for?','What is a compass for? Explícalo en spanglish.'],
  ['Una brújula ayuda a orientarte: su aguja se alinea con el campo magnético terrestre e indica aproximadamente el norte magnético.',
   'A compass helps you find directions: its needle aligns with the Earth’s magnetic field and points approximately toward magnetic north.',
   'Una brújula sirve para orientarte; its needle points approximately toward magnetic north.']),
 ('bookmark',
  ['¿Qué es un marcador del navegador?','What is a browser bookmark?','¿Qué es un browser bookmark? Responde en spanglish.'],
  ['Un marcador guarda la dirección de una página para que puedas volver a abrirla fácilmente. No guarda necesariamente una copia de su contenido.',
   'A browser bookmark saves a page’s address so you can open it again easily. It does not necessarily save a copy of the page itself.',
   'Un marcador guarda la dirección de una página para volver a ella; it does not necessarily save the page’s content.']),
 ('notification',
  ['¿Qué es una notificación?','What is a notification?','Explain a notification, en spanglish.'],
  ['Una notificación es un aviso sobre algo que ocurrió o requiere atención, como la llegada de un mensaje.',
   'A notification is an alert about an event or something that needs attention, such as a new message.',
   'Una notificación es un aviso sobre algo que ocurrió; it might tell you that a new message arrived.']),
 ('update',
  ['¿Para qué sirve actualizar un programa?','Why update a program?','¿Para qué sirve a software update? Responde en spanglish.'],
  ['Una actualización puede corregir errores, solucionar vulnerabilidades o añadir funciones a un programa.',
   'A software update can fix bugs, address vulnerabilities or add features to a program.',
   'Una actualización puede corregir errores o vulnerabilidades; it may also add new features.']),
]
train=[]
for topic,questions,answers in topics:
    for lang,question,answer in zip(['es','en','mixed'],questions,answers):
        train.append({'id':f'knowledge-{topic}-{lang}','language':lang,'request':question,
                      'payload':capture(question,lang),'answer':answer,'synthetic':True})
for index,(level,muted) in enumerate([(7,True),(23,False),(61,True),(94,False),(0,False),(100,True),(48,False),(86,True)]):
    situation={'kind':'operation','operation':'audio.status','polarity':'success','verified':True,'succeeded':True,
               'observed':{'operation':'audio.status','state':{'volumePercent':level,'muted':muted}}}
    questions=['Dime el volumen y si está silenciado.','Tell me the volume and whether audio is muted.','Dime el volumen y el mute status, en spanglish.']
    answers=[f'El volumen está al {level}% y el audio '+('está silenciado.' if muted else 'no está silenciado.'),
             f'The volume is {level}% and audio is '+('muted.' if muted else 'not muted.'),
             (f'El volumen está al {level}%; audio is '+('muted.' if muted else 'not muted.')) if index%2==0 else
             ('Audio is '+('muted' if muted else 'not muted')+f'; el volumen está al {level}%.')]
    for lang,question,answer in zip(['es','en','mixed'],questions,answers):
        train.append({'id':f'audio-{index}-{lang}','language':lang,'request':question,
                      'payload':capture(question,lang,situation),'answer':answer,'synthetic':True,'facts':situation})

holdout=[]
for name,questions,criteria in [
    ('day-night',['¿Por qué hay día y noche?','Why do day and night happen?','Why do we have day and night? Explícalo en spanglish.'],
     'Earth rotates; the side facing the Sun has day and the side facing away has night. No confusion with yearly revolution.'),
    ('heat-metal',['¿Por qué una cuchara metálica se calienta en una sopa caliente?','Why does a metal spoon get hot in hot soup?','¿Por qué se calienta a metal spoon in hot soup? Responde en spanglish.'],
     'Heat transfers from hot soup to the spoon by conduction; no claim that metal creates heat.')]:
    for lang,question in zip(['es','en','mixed'],questions):
        holdout.append({'id':f'{name}-{lang}','language':lang,'request':question,'payload':capture(question,lang),
                        'criteria':criteria,'synthetic':True})
for index,(level,muted) in enumerate([(35,False),(72,True)]):
    situation={'kind':'operation','operation':'audio.status','polarity':'success','verified':True,'succeeded':True,
               'observed':{'operation':'audio.status','state':{'volumePercent':level,'muted':muted}}}
    for lang,question in zip(['es','en','mixed'],['¿A qué volumen está el audio y está silenciado?','What is the audio level, and is it muted?','What is the audio level y está silenciado? Reply in Spanglish.']):
        holdout.append({'id':f'audio-holdout-{index}-{lang}','language':lang,'request':question,
                        'payload':capture(question,lang,situation),'criteria':f'volume={level}%, muted={muted}; read-only, no claim of changing state.',
                        'synthetic':True,'facts':situation})
assert len(train)==48 and len(holdout)==12
assert not ({r['request'] for r in train}&{r['request'] for r in holdout})
for name,rows in [('TRAIN.jsonl',train),('HOLDOUT.jsonl',holdout)]:
    (OUT/name).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
manifest={'kind':'small-synthetic-development-pilot-not-acceptance','trainCount':48,'holdoutCount':12,
          'origin':'Assistant-authored synthetic examples, basic public concepts and invented device states. Never actual PC observations.',
          'separation':'The 12 holdout rows have no training answers and disjoint requests/topics or numeric audio states. Existing development probes remain separately evaluated. None is one of the 100 final acceptance turns.',
          'limits':'Pilot targets language and faithful narration only. Does not certify all eight routes or absence of regression in tool roles.',
          'llmSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
          'files':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['TRAIN.jsonl','HOLDOUT.jsonl']}}
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
