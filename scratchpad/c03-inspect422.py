import json
import os
from pathlib import Path
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product422-private'
samples = json.loads((private/'memory-samples.json').read_text())
peak = max(samples,key=lambda x:sum(p['rss_mib'] for p in x['processes']))
pids = {}
for s in samples:
    for p in s['processes']:
        if p['pid'] not in pids or p['rss_mib']>pids[p['pid']]['rss_mib']:
            pids[p['pid']] = {**p,'elapsed':s['elapsed'],'system_available_mib':s['available_mib']}
report = {'sample_count':len(samples),'peak_rss_sample':peak,'per_process_peaks':list(pids.values()),'minimum_system_available_mib':min(s['available_mib'] for s in samples)}
(private/'memory-attribution.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report,ensure_ascii=False))
events = [json.loads(l) for l in (private/'capture/events.jsonl').open(encoding='utf-8-sig')]
print(json.dumps({'admissions':sum(e['type']=='admission' for e in events),'terminals':[e for e in events if e['type']=='terminal']},ensure_ascii=False))
