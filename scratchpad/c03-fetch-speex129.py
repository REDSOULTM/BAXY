from pathlib import Path
import hashlib
import json
import tarfile
import urllib.request

base = Path('D:/BAXYRuntime/experiments/voice/speexdsp129')
base.mkdir(exist_ok=False)
url = 'https://downloads.xiph.org/releases/speex/speexdsp-1.2.1.tar.gz'
archive = base / 'speexdsp-1.2.1.tar.gz'
with urllib.request.urlopen(url, timeout=45) as response:
    data = response.read(4 * 1024 * 1024)
    assert len(data) < 4 * 1024 * 1024
archive.write_bytes(data)
with tarfile.open(archive) as tar:
    tar.extractall(base, filter='data')
record = {'url': url, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
          'purpose': 'Isolated offline experiment; no runtime registration or source integration'}
(base / 'DOWNLOAD.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record))
