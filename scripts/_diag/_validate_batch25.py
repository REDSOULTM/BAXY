import json, os
base = r'C:/Users/usuario/Desktop/ETC/Programacion/Probando Gemma 4'
inp = os.path.join(base, 'dataset_finetune/curated/batches/_batch_25.jsonl')
out = os.path.join(base, 'dataset_finetune/curated/batches/_batch_25_out.jsonl')
vocab = set('accessibility,app,audio,audio_device,backup_sync,browser,browser_real,clipboard,computer_use,contacts,container,creative_local,data_analysis,database,dependency,desktop_layout,developer,device_settings,document,download,email,env,fact_check,filesystem,form_filler,game_launcher,gui,habit_tracker,input,job_manager,knowledge,local_calendar,local_search,maintenance,media,media_edit,memory,network,notes_tasks,notification,office,package,peripheral,photo_library,printer_scanner,registry,reminder,routine,safety,smart_home,source_manager,state,steam,study,system,terminal,uia,verify,vision,web,whatsapp,window'.split(','))
ii = [json.loads(l) for l in open(inp, encoding='utf-8') if l.strip()]
oo = [json.loads(l) for l in open(out, encoding='utf-8') if l.strip()]
print('input', len(ii), 'output', len(oo))
iid = [r['id'] for r in ii]; oid = [r['id'] for r in oo]
print('order_match', iid == oid)
print('missing', set(iid) - set(oid))
print('extra', set(oid) - set(iid))
req = ['id','user_text','lang','n_steps','correct_tools','also_valid','correct_reply_style','reply_is_template','original_was_correct','correction_reason','confidence','category','source','project']
badf = [(r['id'], [k for k in req if k not in r]) for r in oo if any(k not in r for k in req)]
print('missing_fields', badf)
def flat(x):
    for e in x:
        if isinstance(e, list):
            for s in e: yield s
        else:
            yield e
badv = []
for r in oo:
    for t in list(r['correct_tools']) + list(flat(r['also_valid'])):
        if t not in vocab: badv.append((r['id'], t))
print('out_of_vocab', badv)
from collections import Counter
print('n_steps_dist', dict(Counter(r['n_steps'] for r in oo)))
print('lang', dict(Counter(r['lang'] for r in oo)))
print('orig_correct', dict(Counter(r['original_was_correct'] for r in oo)))
print('category', dict(Counter(r['category'] for r in oo)))
