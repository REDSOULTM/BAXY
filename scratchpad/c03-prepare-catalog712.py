"""Seal the catalog candidate and prepare the same diagnostic with new outputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import textwrap

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-catalog-source712'
assert not out.exists()
source=root/'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
prior=json.loads((base/'astra-window-vocabulary-source705/CANDIDATE4.json').read_text())
assert all(sha(root/name)==value for name,value in prior['sources'].items())
assert sha(source)=='c25571fbca3a506e57576556e3a284d9b38db3902bb1ad3a9f58bfc83c261315'
actual=textwrap.dedent(source.read_text(encoding='utf-8').split('private const string CatalogScript = """\n',1)[1].split('        """;',1)[0])
proposed=(base/'astra-catalog-single-enumeration711/candidate.ps1.txt').read_text(encoding='utf-8')
normalize=lambda s:'\n'.join(line for line in s.splitlines() if not line.strip().startswith('#'))
assert normalize(actual)==normalize(proposed), 'Product script differs from the measured candidate'
out.mkdir()
sources=dict(prior['sources'])
sources[source.relative_to(root).as_posix()]=sha(source)
write(out/'CANDIDATE.json',{'utc':datetime.now(timezone.utc).isoformat(),'adopted':False,
    'parent_commit':prior['parent_commit'],'sources':sources,'python_tree_sha256':prior['python_tree_sha256'],
    'python_files':prior['python_files'],'inherits':'../astra-window-vocabulary-source705/CANDIDATE4.json',
    'change':'Only catalog discovery script uses one existing Shell AppsFolder enumeration for names/IDs and duplicate metadata; diagnostic exception labels no longer name Get-StartApps. Preserves ambiguity checks, cache, cancellation, typed contracts and original Core10s deadline. No new product layer.',
    'evidence':['../astra-fixture-startup-probe709/RESULT.json','../astra-catalog-phases710/RESULT.json','../astra-catalog-single-enumeration711/RESULT.json'],
    'validation_next':'Provider owners, then same50-start diagnostic against the actual fixture with new outputs; remove temporary instrumentation; integrated Full and product73 regression before adoption of combined705+712.',
    'coverage_added':0,'goal_complete':False})
diagnostic=(root/'scratchpad/c03-fixture-startup-probe709.py').read_text(encoding='utf-8')
diagnostic=diagnostic.replace('709','713').replace("'c03-dotnet-diagnostics705/dotnet-stack.exe'","'c03-dotnet-diagnostics705/dotnet-stack.exe'")
diagnostic=diagnostic.replace("'candidate': '../astra-window-vocabulary-source705/CANDIDATE4.json'","'candidate': '../astra-catalog-source712/CANDIDATE.json'")
target=root/'scratchpad/c03-fixture-startup-probe713.py'
assert not target.exists()
target.write_text(diagnostic,encoding='utf-8')
write(out/'DIAGNOSTIC_PARITY.json',{'same_harness':diagnostic.replace('713','709').replace("'candidate': '../astra-catalog-source712/CANDIDATE.json'","'candidate': '../astra-window-vocabulary-source705/CANDIDATE4.json'")==(root/'scratchpad/c03-fixture-startup-probe709.py').read_text(encoding='utf-8'),
    'script_sha256':sha(target),'changed':'Only run identifiers/private and public folders and candidate reference. Same fixture,10s timeout,50maximum,stopfirstfailure,process observation and post-timeout stack capture.'})
print('Candidate712 sealed; diagnostic713 prepared, not executed.')
