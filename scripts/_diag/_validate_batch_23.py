import json, os
VOCAB={'accessibility','app','audio','audio_device','backup_sync','browser','browser_real','clipboard','computer_use','contacts','container','creative_local','data_analysis','database','dependency','desktop_layout','developer','device_settings','document','download','email','env','fact_check','filesystem','form_filler','game_launcher','gui','habit_tracker','input','job_manager','knowledge','local_calendar','local_search','maintenance','media','media_edit','memory','network','notes_tasks','notification','office','package','peripheral','photo_library','printer_scanner','registry','reminder','routine','safety','smart_home','source_manager','state','steam','study','system','terminal','uia','verify','vision','web','whatsapp','window'}
REQ={'id','user_text','lang','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project'}
base=os.path.join(os.path.dirname(__file__),'..','..','dataset_finetune','curated','batches')
inp=[json.loads(l) for l in open(os.path.join(base,'_batch_23.jsonl'),encoding='utf-8') if l.strip()]
out=[json.loads(l) for l in open(os.path.join(base,'_batch_23_out.jsonl'),encoding='utf-8') if l.strip()]
print('in',len(inp),'out',len(out))
assert len(inp)==len(out), 'COUNT MISMATCH'
badvocab=[];missing=[];idmis=[];langs={};tt=0;tf=0
for i,(a,b) in enumerate(zip(inp,out)):
    if a['id']!=b['id']: idmis.append((i,a['id'],b['id']))
    if a['user_text']!=b['user_text']: idmis.append(('usertext',a['id']))
    m=REQ-set(b.keys())
    if m: missing.append((b.get('id'),sorted(m)))
    for t in b['correct_tools']+b['also_valid']:
        if t not in VOCAB: badvocab.append((b['id'],t))
    langs[b['lang']]=langs.get(b['lang'],0)+1
    if b['original_was_correct']: tt+=1
    else: tf+=1
print('idmismatch',idmis)
print('missing_fields',missing)
print('badvocab',badvocab)
print('langs',langs)
print('orig_true',tt,'orig_false',tf)
print('OK' if not (idmis or missing or badvocab) else 'PROBLEMS')
