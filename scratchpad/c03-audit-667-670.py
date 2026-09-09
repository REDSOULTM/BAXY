"""Read-only publication audit; candidate667 remains unadopted."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
home = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
names = [('astra-window-projection667', None),
         ('astra-native-window-projection668', 'C03-native-window-projection668-private'),
         ('astra-projection-product669', 'C03-projection-product669-private'),
         ('astra-native-compound-layers670', 'C03-native-compound-layers670-private')]
pins = 0
for public_name, private_name in names:
    out = base / public_name
    for name, expected in read(out / 'PINS.json').items():
        assert sha(out / name) == expected, (public_name, name)
        relative = (out / name).relative_to(root).as_posix()
        indexed = subprocess.check_output(['git','show',':'+relative], cwd=root)
        assert hashlib.sha256(indexed).hexdigest() == expected, ('index', relative)
        pins += 1
    if private_name:
        for name, expected in read(out / 'RESULT.json')['private_hashes'].items():
            assert sha(home / private_name / name) == expected, (private_name, name)
candidate = read(base / 'astra-window-projection667/RESULT.json')
assert sha(root / 'src/baxy_mind/llm.py') == candidate['source_sha256']
assert sha(root / 'tests/test_c03_window_prose_projection.py') == candidate['test_sha256']
assert sha(Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json') == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert sha(home / 'C03-survey-requirements336-private/requirements.jsonl') == '237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7'
assert subprocess.check_output(['git','rev-parse','main'], cwd=root, text=True).strip() == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
assert subprocess.check_output(['git','branch','--show-current'], cwd=root, text=True).strip() == 'Goal-c03'
running = [p.info['name'] for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('baxy.app.exe','llama-server.exe')]
assert not running, running
print({'public_pins':pins, 'private_hashes':'verified', 'candidate':'preserved, not adopted', 'survey':'unchanged26/716/0', 'main':'unchanged', 'product_processes':running, 'free_ram_mib':round(psutil.virtual_memory().available/2**20,1)})
