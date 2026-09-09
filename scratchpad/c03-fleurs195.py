"""Download four public human diagnostic recordings, not the C03 user reserve."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import urllib.request
import urllib.parse
import subprocess
import wave

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-human195'
assets = Path('D:/BAXYRuntime/experiments/voice/fleurs195')
out.mkdir(exist_ok=False)
assets.mkdir(exist_ok=False)

def save(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def fetch(url):
    with urllib.request.urlopen(url, timeout=45) as response:
        return response.read(10_000_001)

save(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'dataset': 'google/fleurs', 'split': 'test', 'configs': ['es_419', 'en_us'],
    'selection': 'First two rows per locale in row order among first10 with num_samples <=320000 (20s); no recognizer output used to select.',
    'purpose': 'Four human recordings with supplied transcripts for local AEC near-speech controls. Not Carter-to-BAXY requests, fresh reserve, physical near speaker or accepted voice.',
    'source': 'https://huggingface.co/datasets/google/fleurs',
    'apiDocumentation': 'https://huggingface.co/docs/dataset-viewer/en/rows',
    'license': 'CC-BY-4.0; Google FLEURS, Conneau et al. 2022, https://arxiv.org/abs/2205.12446',
    'privacy': 'Only public dataset/config/split names requested; no local text or audio uploaded.',
})
meta = json.loads(fetch('https://huggingface.co/api/datasets/google/fleurs'))
save(out / 'DATASET.json', {'id': meta['id'], 'sha': meta.get('sha'), 'lastModified': meta.get('lastModified')})
manifest = []
for config in ['es_419', 'en_us']:
    query = urllib.parse.urlencode({
        'dataset': 'google/fleurs', 'config': config, 'split': 'test', 'offset': 0, 'length': 10,
    })
    payload = json.loads(fetch('https://datasets-server.huggingface.co/rows?' + query))
    save(assets / f'{config}-rows.json', payload)
    chosen = [r for r in payload['rows'] if r['row']['num_samples'] <= 320000][:2]
    assert len(chosen) == 2
    for item in chosen:
        row = item['row']
        audio = row['audio']
        assert isinstance(audio, list) and len(audio) >= 1, type(audio)
        source = audio[0]['src']
        data = fetch(source)
        assert len(data) < 10_000_000
        target = assets / f'{config}-row{item["row_idx"]}.audio'
        target.write_bytes(data)
        decoded = target.with_suffix('.wav')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(target),
                        '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(decoded)],
                       check=True, capture_output=True)
        with wave.open(str(decoded), 'rb') as wav:
            rate, samples = wav.getframerate(), wav.getnframes()
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        record = {'config': config, 'rowIndex': item['row_idx'], 'id': row['id'],
                  'sourcePath': row['path'], 'rawTranscription': row['raw_transcription'],
                  'transcription': row['transcription'], 'genderLabel': row['gender'],
                  'asset': str(target), 'sha256': hashlib.sha256(data).hexdigest(),
                  'bytes': len(data), 'sampleRate': rate, 'samplesDecoded': samples,
                  'datasetNumSamples': row['num_samples'], 'seconds': samples / rate,
                  'decodedWav': str(decoded), 'decodedSha256': hashlib.sha256(decoded.read_bytes()).hexdigest(),
                  'audioEncoding': audio[0].get('type'), 'conversion': 'ffmpeg to PCM16 mono16000 without gain adjustment'}
        manifest.append(record)
        save(out / 'DOWNLOADS.json', manifest)
        print(json.dumps({k: record[k] for k in ['config','rowIndex','seconds','audioEncoding'] }), flush=True)
save(out / 'COMPLETE.json', {'downloads': len(manifest), 'sourceChanged': False})
