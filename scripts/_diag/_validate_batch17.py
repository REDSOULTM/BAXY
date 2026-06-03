import json
from collections import Counter

VOCAB = set('accessibility app audio audio_device backup_sync browser browser_real clipboard computer_use contacts container creative_local data_analysis database dependency desktop_layout developer device_settings document download email env fact_check filesystem form_filler game_launcher gui habit_tracker input job_manager knowledge local_calendar local_search maintenance media media_edit memory network notes_tasks notification office package peripheral photo_library printer_scanner registry reminder routine safety smart_home source_manager state steam study system terminal uia verify vision web whatsapp window'.split())
REQ = ['id','user_text','lang','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project']
inp='dataset_finetune/curated/batches/_batch_17.jsonl'
out='dataset_finetune/curated/batches/_batch_17_out.jsonl'
in_ids=[json.loads(l)['id'] for l in open(inp,encoding='utf-8') if l.strip()]
rows=[json.loads(l) for l in open(out,encoding='utf-8') if l.strip()]
out_ids=[r['id'] for r in rows]
print('input count:',len(in_ids),'output count:',len(rows))
print('order/id match:',in_ids==out_ids)
bad_vocab=[]; missing=[]
for r in rows:
  for f in REQ:
    if f not in r: missing.append((r['id'],f))
  for t in r['correct_tools']+r['also_valid']:
    if t not in VOCAB: bad_vocab.append((r['id'],t))
print('missing fields:',missing)
print('out-of-vocab tools:',bad_vocab)
print('lang dist:',dict(Counter(r['lang'] for r in rows)))
print('owc true:',sum(1 for r in rows if r['original_was_correct']),'false:',sum(1 for r in rows if not r['original_was_correct']))
print('cat dist:',dict(Counter(r['category'] for r in rows)))
