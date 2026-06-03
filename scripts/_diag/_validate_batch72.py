import json, os
VOCAB={'accessibility','app','audio','audio_device','backup_sync','browser','browser_real','clipboard','computer_use','contacts','container','creative_local','data_analysis','database','dependency','desktop_layout','developer','device_settings','document','download','email','env','fact_check','filesystem','form_filler','game_launcher','gui','habit_tracker','input','job_manager','knowledge','local_calendar','local_search','maintenance','media','media_edit','memory','network','notes_tasks','notification','office','package','peripheral','photo_library','printer_scanner','registry','reminder','routine','safety','smart_home','source_manager','state','steam','study','system','terminal','uia','verify','vision','web','whatsapp','window'}
base=os.path.join(os.path.dirname(__file__),'..','..','dataset_finetune','curated','batches')
inp=[json.loads(l) for l in open(os.path.join(base,'_batch_72.jsonl'),encoding='utf-8') if l.strip()]
out=[json.loads(l) for l in open(os.path.join(base,'_batch_72_out.jsonl'),encoding='utf-8') if l.strip()]
print('in count:',len(inp),'out count:',len(out))
REQ={'id','user_text','lang','n_steps','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project'}
bad_vocab=0; missing=0; order_ok=True; tru=0; fal=0; langs={}
for i,r in enumerate(out):
    mk=REQ-set(r.keys())
    if mk: missing+=1; print('MISSING',r.get('id'),mk)
    for t in r['correct_tools']:
        if t not in VOCAB: bad_vocab+=1; print('BADVOCAB',r['id'],t)
    for av in r['also_valid']:
        for t in av:
            if t not in VOCAB: bad_vocab+=1; print('BADVOCAB-av',r['id'],t)
    if r['id']!=inp[i]['id']: order_ok=False; print('ORDER MISMATCH',i,r['id'],inp[i]['id'])
    if r['original_was_correct'] is True: tru+=1
    else: fal+=1
    langs[r['lang']]=langs.get(r['lang'],0)+1
print('bad_vocab:',bad_vocab,'missing_fields_records:',missing,'order_ok:',order_ok)
print('original_true:',tru,'original_false:',fal)
print('langs:',langs)
