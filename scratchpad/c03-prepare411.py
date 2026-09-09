from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-product404b.py').read_text(encoding='utf-8')
for a, b in [('astra-stored-product404b', 'astra-account-product411'), ('C03-stored-product404b-private', 'C03-account-product411-private'), ('C03-stored-profile404b', 'C03-account-profile411'), ('c03-owner404b-hook', 'c03-owner411-hook')]:
    source = source.replace(a, b)
start = source.index('cases = [')
end = source.index('\ncommands =', start)
cases = ['What is my Windows username?', '¿Con qué cuenta de Windows se está ejecutando BAXY?', 'Which Windows account is running BAXY?', 'Dime la cuenta actual de Windows.', 'Which Windows version am I running?', '¿Qué es una cuenta de Windows?']
source = source[:start] + 'cases = ' + repr(cases) + '\n' + source[end:]
fields = {
    'method': 'Six synthetic development turns through real hidden conductor in a new isolated profile, source410. Four Windows-account requests, one OS version, one account concept. Put English username first to observe actual cold-start limitation known in408; do not wait or inject readiness. Capture all real effects, observations and prose. No response/prompt/decision/catalog override; only same diagnostic local model and read-only HTTP observer. Not fresh acceptance, UI or physical voice.',
    'profile_inheritance': 'New dedicated LOCALAPPDATA/BAXY child; memory remains disabled and no persistence requested. Only authorized read-only identity/OS observations and conceptual conversation. Actual Windows identity values remain in private capture; public adjudication may redact them.',
    'criteria': 'Four account requests perform verified system.identity and describe the effective Windows account, not a human name or OS/resource summary. OS version uses system.status; concept is useful explanation without an unsolicited reading. Cold limitation, omitted literals, wrong subject, false access denial or silent composition fail individually; admission200 does not prove success.',
}
lines = []
for line in source.splitlines():
    key = next((key for key in fields if line.startswith('    ' + repr(key) + ':')), None)
    lines.append('    ' + repr(key) + ':' + repr(fields[key]) + ',' if key else line)
source = '\n'.join(lines) + '\n'
source = source.replace("'src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py'", "'src/Baxy.Kernel/Operations/ProductCatalog.cs','src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py'")
target = root / 'scratchpad/c03-account-product411.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-owner411-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text((root / 'scratchpad/c03-owner404b-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-stored-product404b-private', 'C03-account-product411-private'), encoding='utf-8')
print(json.dumps({'411_cases': len(cases), 'prepared': True}))
