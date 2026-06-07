import json, re
ids = {513, 514, 538, 540, 945}
num_re = re.compile(r'^[\d\.\,\s]+s?%?$')
tok_set = {'Endpoint', 'subprocess', 'qwen3:4b', 'E4B-Q6_K', '/v1/chat/completions',
           'Traceback', 'NoneType', 'stdout', 'stderr', 'localhost', 'async', 'await'}
rows = {}
extra = []
with open('scripts/_diag/_hunt_tanda_0.jsonl', encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        ut = d['user_text'].strip()
        if d['i'] in ids:
            rows[d['i']] = d
        is_num = bool(num_re.match(ut))
        is_tok = ut in tok_set
        is_roleplay = ut.startswith('*') and ut.endswith('*')
        if is_num or is_tok or is_roleplay:
            extra.append((d, 'num' if is_num else 'tok' if is_tok else 'roleplay'))


def fmt(d):
    tools = [t['name'] + '.' + str(t.get('action')) for t in d['tools']]
    return f"i={d['i']:4d} {d['user_text']!r:34} dt={d['dt']:.1f} -> {tools}"


print('=== B3 cited ===')
for i in sorted(ids):
    if i in rows:
        print('  ' + fmt(rows[i]))
print('=== noise-like scan (tanda 1) ===')
for d, kind in sorted(extra, key=lambda x: x[0]['i']):
    print(f'  [{kind:8}] ' + fmt(d))
