import json
from pathlib import Path

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
name='astra-native-primary13';out=base/name;out.mkdir(exist_ok=False)
cases=json.loads((base/'astra-knowledge-budget-integrated8/CASES.json').read_text(encoding='utf-8'))['development']
cases += [{'text_literal':t,'source_references':[],'kind':'synthetic-regression-control'} for t in ["I don't mind, tell me the time",'no abras Steam, dime la hora','no me digas la hora','no uses herramientas, dime la hora','dime la hora']]
(out/'CASES.json').write_text(json.dumps({'development':cases},ensure_ascii=False,indent=2),encoding='utf-8')
(base/f'{name}.turns.jsonl').write_text(''.join(json.dumps({'cmd':'turn','text':r['text_literal']},ensure_ascii=False)+'\n' for r in cases),encoding='utf-8')
script=(root/'scratchpad/c03-audio-endpoint-name3.py').read_text(encoding='utf-8')
script=script.replace('astra-audio-endpoint-name3',name).replace('c03-audio-endpoint-name3','c03-native-primary13')
script=script.replace('Three previously consumed literal audio requests: identify output, read level, read mute.', 'Thirteen development controls: retained knowledge/audio cases plus labeled synthetic negation and clock recovery. Candidate source defaults to native AUTO and removes the second type classifier on that path; all __main__, catalog, argument and Core checks remain. Candidate not accepted until adjudicated; registered assets, no runtime overrides or effect injections.')
(root/'scratchpad/c03-native-primary13.py').write_text(script,encoding='utf-8')
