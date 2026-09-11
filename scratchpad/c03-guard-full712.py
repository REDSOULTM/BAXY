"""Read-only prerequisites for Full after the catalog startup repair."""
import hashlib
import json
from pathlib import Path
import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
candidate=json.loads((base/'astra-catalog-source712/CANDIDATE.json').read_text())
assert all(sha(root/name)==value for name,value in candidate['sources'].items())
startup=json.loads((base/'astra-fixture-startup-probe713/RESULT.json').read_text())
assert startup['ready']==50 and startup['failed_startups']==0
assert startup['fixture_restored'] and startup['temporary_helper_removed']
assert sha(root/'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs')=='628ab599ecae26227707d479220bbab41a06f17e9a3980c828c8dd6c45119ae3'
assert not (root/'tests/Baxy.Integration.Tests/TemporaryStartupProbe713.cs').exists()
smoke=json.loads((base/'astra-core-catalog-smoke715/RESULT.json').read_text())
assert smoke['hello_within10s'] and smoke['seconds']<=10 and smoke['pid_matches'] and smoke['clean_exit_code']==0
assert smoke['application_catalog']=={'verified':True,'complete':True,'names_count':293}
assert json.loads((base/'astra-catalog-source712/PROVIDER_OWNERS_EXIT.json').read_text(encoding='utf-8-sig'))['exit_code']==0
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe','baxy-core.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
print('Full prerequisites verified; source and original deadlines unchanged since candidate seal.')
