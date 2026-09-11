"""Compare a single Shell enumeration with the current catalog script privately."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import textwrap
import time

import psutil

root=Path(__file__).resolve().parents[1]
source=root/'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs'
public=root/'artifacts/comprobaciones/C03/astra-catalog-single-enumeration711'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-catalog-single-enumeration711-private'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not public.exists() and not private.exists()
assert not any(p.info['name'] and p.info['name'].lower() in {'testhost.exe','baxy-core.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
original=textwrap.dedent(source.read_text(encoding='utf-8').split('private const string CatalogScript = """\n',1)[1].split('        """;',1)[0])
candidate=r'''$ErrorActionPreference='Stop'
$utf8=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=$utf8; $OutputEncoding=$utf8
$shell=$null; $folder=$null
try {
    $shell=New-Object -ComObject Shell.Application
    $folder=$shell.NameSpace('shell:AppsFolder')
    if ($null -eq $folder) { throw 'The application namespace is unavailable.' }
    $apps=@(foreach ($item in $folder.Items()) {
        [pscustomobject]@{ Name=$item.Name; AppID=$item.Path; ShellItem=$item }
    })
    $duplicateIds=@{}
    $apps | Group-Object Name | Where-Object Count -GT 1 | ForEach-Object {
        $_.Group | ForEach-Object { $duplicateIds[$_.AppID]=$true }
    }
    $targets=@{}
    try {
        foreach ($app in $apps) {
            if ($duplicateIds.ContainsKey($app.AppID)) {
                $targets[$app.AppID]=$app.ShellItem.ExtendedProperty('System.Link.TargetParsingPath')
            }
        }
    } catch {
        $targets=@{}
    }
    @($apps | ForEach-Object {
        [pscustomobject]@{ Name=$_.Name; AppID=$_.AppID; TargetPath=$targets[$_.AppID] }
    }) | ConvertTo-Json -Compress
} finally {
    if ($null -ne $folder) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($folder) }
    if ($null -ne $shell) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) }
}
'''
public.mkdir();private.mkdir()
(public/'original.ps1.txt').write_text(original,encoding='utf-8')
(public/'candidate.ps1.txt').write_text(candidate,encoding='utf-8')
source_hash=sha(source)
write(public/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source_sha256':source_hash,
    'hypothesis':'Reuse the existing Shell AppsFolder mechanism once for Name/Path and duplicate-target metadata, avoiding the separate Get-StartApps enumeration. No product source changed. Reject if even one original identity/target is lost or altered, or extra entries appear. Exact parity is necessary, not sufficient for adoption.',
    'order':['original','candidate','candidate','original','original','candidate'],'stop':'Stop after the first pair with unequal entries, process error or timeout. Otherwise complete three alternating pairs. No retries to select a winner.',
    'sources':['https://learn.microsoft.com/en-us/windows/win32/shell/shell-namespace','https://learn.microsoft.com/en-us/windows/win32/shell/folder-items'],
    'heritage':'Current provider already enumerates AppsFolder for duplicate metadata. Prior catalog/journal overlap rejected in REGISTRO_DE_MANTENIBILIDAD.md:429-433; no parallelization or cache/fallback proposed.',
    'model_inference':False,'coverage_added':0})
rows=[];entries=[]
for index,kind in enumerate(['original','candidate','candidate','original','original','candidate']):
    script=original if kind=='original' else candidate
    started=time.monotonic()
    with (private/f'{index}-{kind}.stdout.json').open('wb') as output,(private/f'{index}-{kind}.stderr.log').open('wb') as error:
        proc=subprocess.Popen([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoLogo','-NoProfile','-NonInteractive','-Command',script],stdin=subprocess.DEVNULL,stdout=output,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW)
        try:proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait(timeout=5)
            write(public/'TIMEOUT.json',{'index':index,'kind':kind,'seconds':time.monotonic()-started})
            raise
    elapsed=time.monotonic()-started
    path=private/f'{index}-{kind}.stdout.json'
    parsed=json.loads(path.read_text(encoding='utf-8-sig')) if proc.returncode==0 else []
    normalized=sorted((v['Name'],v['AppID'],v.get('TargetPath')) for v in parsed)
    entries.append(normalized)
    digest=hashlib.sha256(json.dumps(normalized,ensure_ascii=False).encode()).hexdigest()
    row={'index':index,'kind':kind,'exit_code':proc.returncode,'seconds':elapsed,'entries':len(parsed),'normalized_entries_sha256':digest,'stdout_sha256':sha(path),'available_ram_mib':psutil.virtual_memory().available/2**20}
    rows.append(row);write(public/'PROGRESS.json',{'runs':rows});print(json.dumps(row),flush=True)
    if proc.returncode!=0:break
    if index%2==1 and entries[-1]!=entries[-2]:
        reference=entries[-2] if rows[-2]['kind']=='original' else entries[-1]
        proposed=entries[-1] if rows[-1]['kind']=='candidate' else entries[-2]
        diff={'missing':sorted(set(reference)-set(proposed)),'extra':sorted(set(proposed)-set(reference))}
        write(private/'ENTRY_DIFFERENCES.json',diff)
        break
result={'runs':rows,'all_entries_identical':len({r['normalized_entries_sha256'] for r in rows})==1,
        'completed_pairs':len(rows)//2,'source_unchanged':sha(source)==source_hash,'adopted':False,'coverage_added':0,'goal_complete':False}
if (private/'ENTRY_DIFFERENCES.json').exists():
    difference=json.loads((private/'ENTRY_DIFFERENCES.json').read_text(encoding='utf-8'))
    result['mismatch_counts']={key:len(value) for key,value in difference.items()}
write(public/'RESULT.json',result)
