"""Localize differences in unchanged198 PCM, using known clean human reference."""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.io import wavfile

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-wave200';out.mkdir(exist_ok=False)
rows=json.loads((base/'astra-human-aec198/RESULTS.json').read_text(encoding='utf-8'))
humans=json.loads((base/'astra-human195/DOWNLOADS.json').read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'Unchanged198 signals against exact human195 source scaled with frozen198 gain. Correct only known algorithm latency: raw0,Speex512,DTLN384 samples; no estimated lag, gain or parameter search. Report full clip and contiguous0.5s blocks. Projection gain, centered correlation and scale-invariant target/residual ratio are diagnostics, not intelligibility or physical acceptance.',
 'onsetSample':31872,'knownDelays':{'raw':0,'speex':512,'dtln128':384},
 'focus':'Second English mixed loses beginning in DTLN readings; first English near-only has blank Parakeet/Speex but full Nemotron. Compare all24 conditions, preserve weak or conflicting metrics.'})
def metrics(reference,output):
    x=reference.astype(np.float64);y=output.astype(np.float64)
    x=x-x.mean();y=y-y.mean()
    xx=float(x@x);yy=float(y@y);xy=float(x@y)
    alpha=xy/max(xx,1e-20)
    projected=alpha*x;residual=y-projected
    ratio=float(projected@projected)/max(float(residual@residual),1e-20)
    return {'targetRms':float(np.sqrt(xx/len(x))),'outputRms':float(np.sqrt(yy/len(y))),
            'correlation':xy/max(np.sqrt(xx*yy),1e-20),'projectionGain':alpha,
            'targetToResidualDb':float(10*np.log10(max(ratio,1e-20)))}
results=[];blocks=[]
for row in rows:
    path=Path(row['privateOutput']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    human=humans[row['human']];original_path=Path(human['asset'])
    assert hashlib.sha256(original_path.read_bytes()).hexdigest()==human['sha256']
    rate,audio=wavfile.read(original_path);assert rate==16000
    reference=audio*row['gain']
    delay={'raw':0,'speex':512,'dtln128':384}[row['engine']]
    with np.load(path) as data:
        signal=data['clean'].ravel()[31872+delay:31872+delay+len(audio)].copy()
    assert len(signal)==len(reference)
    label={k:row[k] for k in ['human','config','id','condition','engine']}
    result={**label,**metrics(reference,signal)}
    results.append(result)
    for first in range(0,len(audio)-7999,8000):
        blocks.append({**label,'firstSecond':first/16000,**metrics(reference[first:first+8000],signal[first:first+8000])})
save(out/'RESULTS.json',results);save(out/'BLOCKS.json',blocks)
save(out/'COMPLETE.json',{'conditions':len(results),'blocks':len(blocks),'sourceChanged':False})
for row in results:
    if row['human']>=2:
        print(json.dumps(row),flush=True)
