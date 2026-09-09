from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.router import _verified_encoder_snapshot
from transformers import AutoTokenizer
from tokenizers import Tokenizer
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-e5-backend547-private'
snapshot,_=_verified_encoder_snapshot()
auto=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True)
direct=Tokenizer.from_file(str(snapshot/'tokenizer.json'))
direct.enable_truncation(max_length=512)
rows=json.loads((private/'queries.json').read_text(encoding='utf-8'))
differences=[]
for row in rows:
    text='query: '+row['text']
    expected=auto(text,truncation=True,max_length=512)['input_ids']
    actual=direct.encode(text).ids
    if expected!=actual:
        stripped=direct.encode(text.strip()).ids
        differences.append({'case_id':row['case_id'],'auto_length':len(expected),
          'direct_length':len(actual),'strip_matches':expected==stripped,
          'auto_tail':expected[-8:],'direct_tail':actual[-8:]})
report={'auto_class':type(auto).__name__,'direct_differences':differences,
        'direct_backend_json_matches':auto.backend_tokenizer.to_str()==direct.to_str()}
effective=json.loads(auto.backend_tokenizer.to_str())
raw=json.loads(direct.to_str())
report['changed_backend_fields']={key:{'auto':effective[key],'raw':raw[key]} for key in effective if effective[key]!=raw[key] and key!='model'}
(private/'effective-tokenizer548.json').write_text(auto.backend_tokenizer.to_str(),encoding='utf-8',newline='\n')
path=root/'artifacts/comprobaciones/C03/astra-e5-backend547/TOKENIZER_DIAGNOSIS548.json'
path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report))
