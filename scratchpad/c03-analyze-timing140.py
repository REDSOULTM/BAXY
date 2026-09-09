from pathlib import Path
import hashlib
import json
import os
import numpy as np

root = Path(__file__).resolve().parents[1]
source = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice139-private'
metadata = json.loads((source/'timing139.json').read_text(encoding='utf-8'))
data = np.load(source/'timing139.npz')
blocks = data['loop'].reshape(-1,512)
hashes = [hashlib.sha256(block.tobytes()).hexdigest() for block in blocks]
rows = []
previous = None
for index, (record, reference) in enumerate(zip(metadata['processes'], data['reference'], strict=True)):
    digest = hashlib.sha256(reference[-512:].tobytes()).hexdigest()
    available = min(record['callbacksSeen'],len(hashes))
    matches = [i for i in range(max(0,available-32),available) if hashes[i] == digest]
    matched = matches[-1] if matches else None
    rms = float(np.sqrt(np.mean(reference[-512:].astype(np.float64)**2)))
    delta = matched-previous if matched is not None and previous is not None else None
    rows.append({'frame':index,'utc':record['utc'],'matchedCallback':matched,
                 'referenceRmsPcm':rms,'deltaCallback':delta,
                 'micReadAvailable':metadata['reads'][index]['micReadAvailable']})
    previous = matched
active = [row for row in rows if row['referenceRmsPcm'] >=20]
def counts(values):
    return {str(key):int(value) for key,value in zip(*np.unique(values,return_counts=True))}
result = {'micFrames':len(rows),'loopCallbacks':len(blocks),
          'activeReferenceFrames':len(active),
          'allMatchedDeltaCounts':counts([r['deltaCallback'] for r in rows if r['deltaCallback'] is not None]),
          'activeMatchedDeltaCounts':counts([r['deltaCallback'] for r in active if r['deltaCallback'] is not None]),
          'micLatencySeconds':sorted(set(r['micLatency'] for r in metadata['reads'])),
          'loopLatencySeconds':sorted(set(r['loopLatency'] for r in metadata['reads'])),
          'limit':'Hash matching proves repeated/skipped actual reference blocks at consumer. It does not alone establish true ADC alignment; micTime minus latency/backlog is only an estimate.',
          'rows':rows}
target = source/'timing140.json'
with target.open('x',encoding='utf-8') as f:
    json.dump(result,f,indent=2)
out = root/'artifacts/comprobaciones/C03/astra-voice139'
with (out/'TIMING_INDEX.json').open('x',encoding='utf-8') as f:
    json.dump({'files':[{'privatePath':str(source/name),'sha256':hashlib.sha256((source/name).read_bytes()).hexdigest()} for name in ['timing139.json','timing139.npz','timing140.json']]},f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k != 'rows'},indent=2))
