"""Bounded phase timing of the existing catalogue script, without product edits."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import textwrap
import time

import psutil

root = Path(__file__).resolve().parents[1]
source = root / 'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs'
public = root / 'artifacts/comprobaciones/C03/astra-catalog-phases710'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-catalog-phases710-private'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p,v: p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not public.exists() and not private.exists()
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe','baxy-core.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
original = textwrap.dedent(source.read_text(encoding='utf-8').split('private const string CatalogScript = """\n',1)[1].split('        """;',1)[0])
def marker(name):
    return "[Console]::Error.WriteLine('C03PHASE|"+name+"|' + $c03PhaseClock.Elapsed.TotalMilliseconds.ToString([Globalization.CultureInfo]::InvariantCulture))\n"
timed = '$c03PhaseClock=[Diagnostics.Stopwatch]::StartNew()\n'+marker('script_started')+original
for anchor,name in [('$apps=@(Get-StartApps)\n','start_apps_complete'),('$targets=@{}\n','duplicates_grouped'),
                    ('@($apps | ForEach-Object {\n','shell_metadata_complete')]:
    assert anchor in timed
    if name == 'shell_metadata_complete': timed=timed.replace(anchor,marker(name)+anchor,1)
    else: timed=timed.replace(anchor,anchor+marker(name),1)
timed += marker('serialization_complete')
public.mkdir()
private.mkdir()
(public/'original-script.ps1.txt').write_text(original,encoding='utf-8')
(public/'timed-script.ps1.txt').write_text(timed,encoding='utf-8')
source_hash=sha(source)
write(public/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source_sha256':source_hash,
    'method':'Three alternating original/instrumented pairs of the existing PowerShell catalog script, copied exactly from source. Only stopwatch and stderr phase markers added. No providers, models, user turns, or source edits. Compare full JSON entries privately; publish timing, count and hashes only. The standalone observation cap40s is not a change to the Core handshake10s.',
    'order':['original','timed','timed','original','original','timed'],'coverage_added':0,
    'sources':['https://learn.microsoft.com/en-us/powershell/module/startlayout/get-startapps?view=windowsserver2025-ps'],
    'source_note':'Official Get-StartApps documents name/AppID enumeration; local timing must identify the cause, documentation does not promise a startup SLA.'})
rows=[]
for index,kind in enumerate(['original','timed','timed','original','original','timed']):
    script=original if kind=='original' else timed
    began=time.monotonic()
    with (private/f'{index}-{kind}.stdout.json').open('wb') as output, (private/f'{index}-{kind}.stderr.log').open('wb') as error:
        proc=subprocess.Popen([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
            '-NoLogo','-NoProfile','-NonInteractive','-Command',script],stdin=subprocess.DEVNULL,stdout=output,stderr=error,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try: proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            write(public/'TIMEOUT.json',{'index':index,'kind':kind,'seconds':time.monotonic()-began})
            raise
    seconds=time.monotonic()-began
    out=private/f'{index}-{kind}.stdout.json'
    errors=(private/f'{index}-{kind}.stderr.log').read_text(encoding='utf-8-sig')
    phases={}
    for line in errors.splitlines():
        if line.startswith('C03PHASE|'):
            _,name,value=line.split('|')
            phases[name]=float(value)/1000
    parsed=json.loads(out.read_text(encoding='utf-8-sig')) if proc.returncode==0 else []
    normalized=sorted((v['Name'],v['AppID'],v.get('TargetPath')) for v in parsed)
    digest=hashlib.sha256(json.dumps(normalized,ensure_ascii=False).encode()).hexdigest()
    row={'index':index,'kind':kind,'exit_code':proc.returncode,'seconds':seconds,'phases_seconds':phases,
         'entries':len(parsed),'normalized_entries_sha256':digest,'stdout_sha256':sha(out),
         'available_ram_mib':psutil.virtual_memory().available/2**20}
    rows.append(row)
    write(public/'PROGRESS.json',{'runs':rows})
    print(json.dumps(row),flush=True)
    assert proc.returncode==0
write(public/'RESULT.json',{'runs':rows,'all_entries_identical':len({r['normalized_entries_sha256'] for r in rows})==1,
    'source_unchanged':sha(source)==source_hash,'median_total_seconds':{k:statistics.median(r['seconds'] for r in rows if r['kind']==k) for k in ['original','timed']},
    'model_inference':False,'coverage_added':0,'goal_complete':False})
