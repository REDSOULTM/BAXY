"""Second pilot: add history and compound verified results, without consuming holdout answers."""
from pathlib import Path
import copy
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from baxy_mind.llm import LlmRuntime
OUT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot2-data'
PARENT=ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot-data'
assert not OUT.exists();OUT.mkdir()
class Captured(Exception):pass
class Recorder(LlmRuntime):
    def __init__(self):self._gguf='Qwen3-4B-Instruct-2507-Q4_K_M.gguf';self.payload=None
    def _post(self,payload):self.payload=copy.deepcopy(payload);raise Captured()
train=[json.loads(line) for line in (PARENT/'TRAIN.jsonl').read_text(encoding='utf-8').splitlines()]
holdout=[json.loads(line) for line in (PARENT/'HOLDOUT.jsonl').read_text(encoding='utf-8').splitlines()]
history=[{'role':'user','content':'What is a triangle?'},{'role':'assistant','content':'A triangle is a shape with three straight sides.'},
         {'role':'user','content':'And a square?'},{'role':'assistant','content':'A square has four equal sides and four right angles.'}]
for original in list(train):
    if not original['id'].startswith('knowledge-'):continue
    row=copy.deepcopy(original);row['id']='with-history-'+row['id']
    recorder=Recorder()
    try:recorder.chat(row['request'],history=history,conversation_kind='knowledge',response_language=row['language'])
    except Captured:pass
    assert recorder.payload;row['payload']=recorder.payload;row['history']=history;train.append(row)

def compound(level,muted,clock,request):
    observed={'utc':'2026-01-01T'+clock+':00+00:00','localUtcOffsetMinutes':0}
    steps=[{'kind':'operation','operation':'system.time','polarity':'success','verified':True,'succeeded':True,'observed':observed,'readOnly':True},
           {'kind':'operation','operation':'audio.status','polarity':'success','verified':True,'succeeded':True,
            'observed':{'operation':'audio.status','state':{'volumePercent':level,'muted':muted}},'readOnly':True}]
    situation={'kind':'status','polarity':'success','cause':'mission_completed','stepCount':2,
               'steps':[json.dumps(s) for s in steps],'completedRequest':request,
               'observed':dict(observed,muted=muted,level=level)}
    recorder=Recorder()
    try:recorder.compose_user_message(request,'status',{'situation':json.dumps(situation)})
    except Captured:pass
    assert recorder.payload
    return recorder.payload,situation

for index,(level,muted,clock) in enumerate([(52,False,'06:43'),(18,True,'19:26'),(79,False,'10:57'),(41,True,'22:09')]):
    questions=['¿Qué hora es y cómo está el sonido?','What time is it, and what is the audio state?',
               'Tell me the time y cómo está el sonido, en spanglish.']
    answers=[f'Son las {clock}; el volumen está al {level}% y el audio '+('está silenciado.' if muted else 'no está silenciado.'),
             f'The time is {clock}; the volume is {level}% and audio is '+('muted.' if muted else 'not muted.'),
             f'Son las {clock} y el volumen está al {level}%; audio is '+('muted.' if muted else 'not muted.')]
    for lang,question,answer in zip(['es','en','mixed'],questions,answers):
        payload,situation=compound(level,muted,clock,question)
        train.append({'id':f'compound-{index}-{lang}','language':lang,'request':question,'payload':payload,
                      'answer':answer,'synthetic':True,'facts':situation})
for index,(level,muted,clock) in enumerate([(64,False,'08:36'),(29,True,'16:47')]):
    for lang,question in zip(['es','en','mixed'],['Dime qué hora es, el volumen y si el sonido está silenciado.',
        'Give me the time, volume and mute status.','¿Qué hora es? Also tell me the volume and mute status, en spanglish.']):
        payload,situation=compound(level,muted,clock,question)
        holdout.append({'id':f'compound-heldout-{index}-{lang}','language':lang,'request':question,'payload':payload,
                        'criteria':f'Time={clock},volume={level}%,muted={muted}; read only, no state changes; requested language.',
                        'synthetic':True,'facts':situation})
assert len(train)==84 and len(holdout)==18
assert not ({r['request'] for r in train}&{r['request'] for r in holdout})
for name,rows in [('TRAIN.jsonl',train),('HOLDOUT.jsonl',holdout)]:
    (OUT/name).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
manifest={'kind':'second-synthetic-development-pilot-not-acceptance','trainCount':84,'holdoutCount':18,
          'hypothesis':'Pilot1 improves single audio observations but fails compound outcomes and history. Add those input structures, preserving typed facts and varied user languages. Do not train on heldout answers or the nine previous failure questions.',
          'unchanged':'Same base, LoRA rank, sampling at evaluation and training hyperparameters. The data coverage is the experimental change.',
          'origin':'48 original authored examples + 24 history variants + 12 synthetic compound-state examples. 12 prior holdout remain untrained; six new compound holdout frozen before training.',
          'files':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['TRAIN.jsonl','HOLDOUT.jsonl']}}
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
runner=(ROOT/'scratchpad/c03-train-lora-pilot.py').read_text(encoding='utf-8')
runner=runner.replace('48-example','84-example').replace('astra-lora-pilot-training','astra-lora-pilot2-training').replace('c03-pilot-lora-v1','c03-pilot-lora-v2').replace('astra-lora-pilot-data','astra-lora-pilot2-data')
target=ROOT/'scratchpad/c03-train-lora-pilot2.py'
assert not target.exists();target.write_text(runner,encoding='utf-8')
