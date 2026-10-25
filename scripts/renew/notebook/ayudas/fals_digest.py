import json, os, sys
R = os.environ.get('BAXY_RENEW_BANKS', 'D:/BAXYeval/renew_v1') + '/runs/'  # PC-Q: as the other scripts
pairs = {'s3': ('nb-lote-A-fals-s3', 'nb-lote-B-fals-s3'), 's4': ('nb-lote-A-fals-s4', 'nb-lote-B-fals-s4'), 's5': ('nb-lote-A-fals-s5', 'nb-lote-B-fals-s5'), 's0': ('nb-comb1-A-fals-s0', 'nb-comb1-B-fals-s0'), 's1': ('nb-lote-A-fals-s1', 'nb-lote-B-fals-s1'),
         's2': ('nb-lote-A-fals-s2', 'nb-lote-B-fals-s2')}
def brief_obs(o):
    try: d = json.loads(o or '{}')
    except Exception: return ''
    ob = d.get('observed') or {}
    keep = {k: v for k, v in ob.items() if k in ('fullPath', 'path', 'foreground', 'alreadyRunning', 'count', 'closed', 'state', 'applicationName', 'next', 'scope', 'notAvailableYet', 'folder', 'sameNameInHome', 'placeRequested', 'text', 'title', 'level', 'value', 'mode', 'windowFrom', 'reason')}
    s = json.dumps(keep, ensure_ascii=False)
    return s[:220]
def turns(label):
    t = json.load(open(R + label + '-falsedades/transcripts.json', encoding='utf-8'))
    return {c['id']: c for c in t}
seed = sys.argv[1]
print(f"runs: {R} (banks {'BAXY_RENEW_BANKS' if os.environ.get('BAXY_RENEW_BANKS') else 'default'})", flush=True)  # PC-Q: another BAXY_RENEW_BANKS read other runs silently
A, B = (turns(x) for x in pairs[seed])
for cid in sorted(A):
    print(f'#### {cid} {seed} | trap: {A[cid]["trap"][:160]}')
    for arm, run in (('A', A), ('B', B)):
        for n, tr in enumerate(run[cid]['turns']):
            out = []
            for ev in tr['ordered']:
                if ev['kind'] == 'person': out.append(f'P: {ev["text"][:140]}')
                elif ev['kind'] == 'step':
                    args = json.dumps(ev.get('arguments') or {}, ensure_ascii=False)[:110]
                    out.append(f'  > {ev["operation"]} {args} = {ev["status"]}{"/" + ev["error"] if ev.get("error") else ""} {brief_obs(ev.get("observed"))}')
                elif ev['kind'] == 'baxy': out.append(f'  BAXY: {ev["text"][:300]}')
            print(f' [{arm} t{n}] ' + '\n'.join(out))
