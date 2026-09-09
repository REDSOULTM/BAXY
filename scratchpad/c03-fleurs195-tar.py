"""Read a bounded prefix of the author's archive; retain four original WAVs."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib
import io
import json
import tarfile
import urllib.request
import numpy as np
from scipy.io import wavfile

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-human195'
assets = Path('D:/BAXYRuntime/experiments/voice/fleurs195')
meta = json.loads((out / 'DATASET.json').read_text(encoding='utf-8'))
revision = meta['sha']

def save(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

save(out / 'PREREG-TAR.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'revision': revision,
    'reasonForAccessChange': 'Dataset viewer rows and first-rows return HTTP500:703MB row group exceeds300MB scan limit. No recordings or recognizer outputs obtained by that attempt.',
    'selection': 'First two distinct transcript IDs per locale in author tar member order with metadata duration <=20s. Stop at100 members or64MiB compressed input; no choice by recognized text or quality.',
    'locales': ['es_419','en_us'], 'split': 'test',
    'method': 'Read original WAV bytes directly from pinned archive without unpacking filesystem paths. Read public TSV for expected text. Preserve native audio; no gain or resampling.',
    'license': 'Google FLEURS, Conneau et al.2022, CC-BY-4.0; https://huggingface.co/datasets/google/fleurs; https://arxiv.org/abs/2205.12446',
    'limitation': 'Human read speech for AEC diagnostics, not user requests, physical microphone acceptance or the C03 reserved100.',
})

class BoundedReader:
    def __init__(self, handle): self.handle, self.count = handle, 0
    def read(self, size):
        assert self.count + size <= 64 * 1024 * 1024, 'Compressed prefix budget exceeded'
        data = self.handle.read(size)
        self.count += len(data)
        return data

manifest = []
for config in ['es_419','en_us']:
    prefix = f'https://huggingface.co/datasets/google/fleurs/resolve/{revision}/data/{config}'
    tsv = assets / f'{config}-test.tsv'
    if not tsv.exists():
        with urllib.request.urlopen(prefix + '/test.tsv', timeout=45) as response:
            data = response.read(2_000_001)
        assert len(data) < 2_000_000
        tsv.write_bytes(data)
    records = {}
    for line in tsv.read_text(encoding='utf-8').splitlines():
        cols = line.split('\t')
        assert len(cols) == 7
        records[cols[1]] = cols
    selected_ids = set()
    url = prefix + '/audio/test.tar.gz'
    with urllib.request.urlopen(url, timeout=45) as response:
        reader = BoundedReader(response)
        with tarfile.open(fileobj=reader, mode='r|gz') as archive:
            for index, member in enumerate(archive):
                assert index < 100, 'Member count budget exceeded'
                name = PurePosixPath(member.name).name
                if not member.isfile() or name not in records:
                    continue
                cols = records[name]
                if int(cols[5]) > 320000 or cols[0] in selected_ids:
                    continue
                assert member.size < 5_000_000
                with archive.extractfile(member) as handle:
                    audio = handle.read()
                rate, signal = wavfile.read(io.BytesIO(audio))
                assert rate == 16000 and signal.ndim == 1
                assert len(signal) == int(cols[5])
                target = assets / f'{config}-{name}'
                assert not target.exists()
                target.write_bytes(audio)
                record = {'config': config, 'id': cols[0], 'archiveMemberIndex': index,
                          'archiveMember': member.name, 'sourceUrl': url, 'revision': revision,
                          'rawTranscription': cols[2], 'transcription': cols[3], 'genderLabel': cols[6],
                          'asset': str(target), 'sha256': hashlib.sha256(audio).hexdigest(),
                          'bytes': len(audio), 'sampleRate': rate, 'samples': len(signal),
                          'seconds': len(signal)/rate, 'dtype': str(signal.dtype),
                          'peakNative': float(np.max(np.abs(signal.astype(np.float64)))),
                          'tsvSha256': hashlib.sha256(tsv.read_bytes()).hexdigest()}
                manifest.append(record)
                selected_ids.add(cols[0])
                save(out / 'DOWNLOADS.json', manifest)
                print(json.dumps({k: record[k] for k in ['config','id','archiveMemberIndex','seconds','dtype','peakNative']}), flush=True)
                if len(selected_ids) == 2:
                    break
        assert len(selected_ids) == 2
        save(out / f'{config}-TRANSFER.json', {'compressedBytesRead': reader.count, 'completeArchiveDownloaded': False, 'selectedFiles': 2})
save(out / 'COMPLETE.json', {'downloads': len(manifest), 'sourceChanged': False})
