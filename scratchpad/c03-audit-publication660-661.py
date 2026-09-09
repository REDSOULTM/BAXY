"""Read-only audit of sealed bytes and the exact staged candidate."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
sha = lambda data: hashlib.sha256(data).hexdigest()
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
staged = '--staged' in sys.argv
assert subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip() == 'Goal-c03'
assert subprocess.check_output(['git','rev-parse','main'],cwd=root,text=True).strip() == '5f572ee1b48cb5e2543ee5e06510e51057c9c845'
verified = 0
for name in ['window-facts-source660','window-facts-product661']:
    out = base / ('astra-' + name)
    for filename, digest in read(out / 'PINS.json').items():
        path = out / filename
        assert sha(path.read_bytes()) == digest, path
        if staged:
            assert sha(subprocess.check_output(['git','show',':'+path.relative_to(root).as_posix()],cwd=root)) == digest, path
        verified += 1
    private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-window-facts-product661-private'
    for filename, digest in read(out / 'RESULT.json')['private_hashes'].items():
        assert sha((private / filename).read_bytes()) == digest
for name, digest in read(base / 'astra-window-facts-source660/PREREG.json')['sources'].items():
    data = (root / name).read_bytes()
    assert sha(data) == digest
    if staged:
        assert subprocess.check_output(['git','show',':'+name],cwd=root).replace(b'\r\n',b'\n') == data.replace(b'\r\n',b'\n')
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest.read_bytes()) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
survey = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-survey-requirements336-private/requirements.jsonl'
assert sha(survey.read_bytes()) == '237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7'
print({'verified_public_pins':verified,'staged':staged,'sources_validated':True,'manifest_survey_main_unchanged':True})
