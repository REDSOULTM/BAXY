import json, os
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
vocab = set('accessibility app audio audio_device backup_sync browser browser_real clipboard computer_use contacts container creative_local data_analysis database dependency desktop_layout developer device_settings document download email env fact_check filesystem form_filler game_launcher gui habit_tracker input job_manager knowledge local_calendar local_search maintenance media media_edit memory network notes_tasks notification office package peripheral photo_library printer_scanner registry reminder routine safety smart_home source_manager state steam study system terminal uia verify vision web whatsapp window'.split())
req = ['id','user_text','lang','n_steps','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project']
inp=[json.loads(l) for l in open('dataset_finetune/curated/batches/_batch_08.jsonl',encoding='utf-8') if l.strip()]
out=[json.loads(l) for l in open('dataset_finetune/curated/batches/_batch_08_out.jsonl',encoding='utf-8') if l.strip()]
print('in',len(inp),'out',len(out))
assert [r['id'] for r in inp]==[r['id'] for r in out], 'ID/order mismatch'
badtool=0; missing=0; langs={}; tcorrect=0; tfalse=0
for r in out:
    for f in req:
        if f not in r: missing+=1; print('MISSING',f,r['id'])
    for t in r['correct_tools']+r['also_valid']:
        if t not in vocab: badtool+=1; print('BADTOOL',t,r['id'])
    langs[r['lang']]=langs.get(r['lang'],0)+1
    if r['original_was_correct']: tcorrect+=1
    else: tfalse+=1
print('badtool',badtool,'missing',missing)
print('orig_correct_true',tcorrect,'false',tfalse)
print('langs',langs)
