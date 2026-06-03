import json
from collections import Counter

VOCAB = {'accessibility','app','audio','audio_device','backup_sync','browser','browser_real','clipboard','computer_use','contacts','container','creative_local','data_analysis','database','dependency','desktop_layout','developer','device_settings','document','download','email','env','fact_check','filesystem','form_filler','game_launcher','gui','habit_tracker','input','job_manager','knowledge','local_calendar','local_search','maintenance','media','media_edit','memory','network','notes_tasks','notification','office','package','peripheral','photo_library','printer_scanner','registry','reminder','routine','safety','smart_home','source_manager','state','steam','study','system','terminal','uia','verify','vision','web','whatsapp','window'}
req = {'id','user_text','lang','n_steps','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project'}

base = r'dataset_finetune/curated/batches'
inp = [json.loads(l) for l in open(base + '/_batch_32.jsonl', encoding='utf-8') if l.strip()]
out = [json.loads(l) for l in open(base + '/_batch_32_out.jsonl', encoding='utf-8') if l.strip()]
print('in', len(inp), 'out', len(out))
assert len(inp) == len(out), 'COUNT MISMATCH'
for i, (a, b) in enumerate(zip(inp, out)):
    assert a['id'] == b['id'], f'ORDER MISMATCH at {i}: {a["id"]} vs {b["id"]}'
badvocab = []
miss = []
for b in out:
    m = req - set(b.keys())
    if m:
        miss.append((b['id'], m))
    for t in b['correct_tools'] + b['also_valid']:
        if t not in VOCAB:
            badvocab.append((b['id'], t))
print('missing_fields', miss)
print('out_of_vocab', badvocab)
print('langs', dict(Counter(b['lang'] for b in out)))
print('orig_true', sum(1 for b in out if b['original_was_correct']))
print('orig_false', sum(1 for b in out if not b['original_was_correct']))
print('categories', dict(Counter(b['category'] for b in out)))
print('ALL OK' if not miss and not badvocab else 'PROBLEMS FOUND')
