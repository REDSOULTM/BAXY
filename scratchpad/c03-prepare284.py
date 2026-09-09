from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-account284'
before = out / 'before'
before.mkdir(exist_ok=False)
source = root / 'src/baxy_mind/llm.py'
shutil.copy2(source, before / 'llm.py')
prereg = {'utc': datetime.now(timezone.utc).isoformat(),
    'hypothesis': 'A Core-observed account identity is a required fact of its public result. Existing guard already checks other observed values; extend it to the actual userName field using exact token boundaries and original accents.',
    'nativeEvidence': 'astra-identity283/RESULT.json: same initial payload, before Hola soy BAXY; dynamic observed-name guard gives Tu nombre de usuario en el sistema es usuario.',
    'scope': 'Fact conservation only. Does not claim personal-name memory works, change operation selection, or broaden authority. No response literal, account constant, new prompt or sampler.',
    'validation': 'Observed account/partial-name/Unicode/absent-value controls and actual compose retry; owning compose/transport/turn suites. Integrated Fast/UI remains separately required.',
    'sourceBeforeSha256': hashlib.sha256(source.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
