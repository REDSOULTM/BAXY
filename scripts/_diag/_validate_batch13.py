import json
from collections import Counter

vocab = set('accessibility app audio audio_device backup_sync browser browser_real clipboard computer_use contacts container creative_local data_analysis database dependency desktop_layout developer device_settings document download email env fact_check filesystem form_filler game_launcher gui habit_tracker input job_manager knowledge local_calendar local_search maintenance media media_edit memory network notes_tasks notification office package peripheral photo_library printer_scanner registry reminder routine safety smart_home source_manager state steam study system terminal uia verify vision web whatsapp window'.split())
req = ['id', 'user_text', 'lang', 'n_steps', 'correct_tools', 'also_valid', 'correct_reply_style', 'reply_is_template', 'original_was_correct', 'correction_reason', 'confidence', 'category', 'source', 'project']
base = r'C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\dataset_finetune\curated\batches' + '\\'
inp = [json.loads(l) for l in open(base + '_batch_13.jsonl', encoding='utf-8') if l.strip()]
out = [json.loads(l) for l in open(base + '_batch_13_out.jsonl', encoding='utf-8') if l.strip()]
print('input count', len(inp), 'output count', len(out))
assert [r['id'] for r in inp] == [r['id'] for r in out], 'ID/order mismatch'
bad = []
for r in out:
    for f in req:
        if f not in r:
            bad.append((r['id'], 'missing ' + f))
    for t in r['correct_tools'] + r['also_valid']:
        if t not in vocab:
            bad.append((r['id'], 'BADVOCAB ' + t))
print('problems:', bad)
ct = sum(1 for r in out if r['original_was_correct'])
print('owc true:', ct, 'false:', len(out) - ct)
print('lang:', dict(Counter(r['lang'] for r in out)))
print('category:', dict(Counter(r['category'] for r in out)))
print('templates:', sum(1 for r in out if r['reply_is_template']))
