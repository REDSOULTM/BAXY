import json, os
os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))
VOCAB={'accessibility','app','audio','audio_device','backup_sync','browser','browser_real','clipboard','computer_use','contacts','container','creative_local','data_analysis','database','dependency','desktop_layout','developer','device_settings','document','download','email','env','fact_check','filesystem','form_filler','game_launcher','gui','habit_tracker','input','job_manager','knowledge','local_calendar','local_search','maintenance','media','media_edit','memory','network','notes_tasks','notification','office','package','peripheral','photo_library','printer_scanner','registry','reminder','routine','safety','smart_home','source_manager','state','steam','study','system','terminal','uia','verify','vision','web','whatsapp','window'}
REQ={'id','user_text','lang','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project'}
inp=[json.loads(l) for l in open('dataset_finetune/curated/batches/_batch_24.jsonl',encoding='utf-8') if l.strip()]
out=[json.loads(l) for l in open('dataset_finetune/curated/batches/_batch_24_out.jsonl',encoding='utf-8') if l.strip()]
print('input records:',len(inp),'output records:',len(out))
assert len(inp)==len(out), 'COUNT MISMATCH'
ct=cf=0; langs={}; oob=[]
for i,(a,b) in enumerate(zip(inp,out)):
    assert a['id']==b['id'], 'ID MISMATCH at %d'%i
    missing=REQ-set(b.keys())
    assert not missing, 'MISSING %s %s'%(b['id'],missing)
    for t in b['correct_tools']+b['also_valid']:
        if t not in VOCAB: oob.append((b['id'],t))
    if b['original_was_correct']: ct+=1
    else: cf+=1
    langs[b['lang']]=langs.get(b['lang'],0)+1
    assert isinstance(b['correct_tools'],list) and isinstance(b['also_valid'],list)
    assert isinstance(b['original_was_correct'],bool) and isinstance(b['reply_is_template'],bool)
    assert isinstance(b['confidence'],(int,float))
print('out-of-vocab:',oob)
print('owc True:',ct,'False:',cf)
print('langs:',langs)
print('ALL CHECKS PASSED')
