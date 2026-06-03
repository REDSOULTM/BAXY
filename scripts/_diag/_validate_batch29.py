import json
VOCAB={'accessibility','app','audio','audio_device','backup_sync','browser','browser_real','clipboard','computer_use','contacts','container','creative_local','data_analysis','database','dependency','desktop_layout','developer','device_settings','document','download','email','env','fact_check','filesystem','form_filler','game_launcher','gui','habit_tracker','input','job_manager','knowledge','local_calendar','local_search','maintenance','media','media_edit','memory','network','notes_tasks','notification','office','package','peripheral','photo_library','printer_scanner','registry','reminder','routine','safety','smart_home','source_manager','state','steam','study','system','terminal','uia','verify','vision','web','whatsapp','window'}
inp='dataset_finetune/curated/batches/_batch_29.jsonl'
out='dataset_finetune/curated/batches/_batch_29_out.jsonl'
in_ids=[json.loads(l)['id'] for l in open(inp,encoding='utf-8') if l.strip()]
rows=[json.loads(l) for l in open(out,encoding='utf-8') if l.strip()]
out_ids=[r['id'] for r in rows]
fields={'id','user_text','lang','n_steps','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project'}
bad_vocab=[]; missing=[]; badtype=[]
for r in rows:
    miss=fields-set(r.keys())
    if miss: missing.append((r['id'],list(miss)))
    for t in r['correct_tools']:
        if t not in VOCAB: bad_vocab.append((r['id'],t))
    for av in r['also_valid']:
        for t in av:
            if t not in VOCAB: bad_vocab.append((r['id'],'also:'+t))
    if not isinstance(r['n_steps'],int): badtype.append((r['id'],'n_steps'))
print('in count',len(in_ids),'out count',len(rows))
print('ids match order:',in_ids==out_ids)
print('missing fields:',missing)
print('bad vocab:',bad_vocab)
print('bad types:',badtype)
from collections import Counter
print('langs:',dict(Counter(r['lang'] for r in rows)))
print('orig true:',sum(1 for r in rows if r['original_was_correct']))
print('orig false:',sum(1 for r in rows if not r['original_was_correct']))
print('categories:',dict(Counter(r['category'] for r in rows)))
