"""Read immutable Git snapshots; build an isolated, effect-free forensic probe."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8-sig')

snapshots = {}
def snapshot(ref: str, path: str) -> str:
    source = git('show', f'{ref}:{path}')
    destination = OUT / 'snapshots' / ref / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source, encoding='utf-8', newline='\n')
    snapshots[f'{ref}:{path}'] = {
        'commit': git('rev-parse', ref).strip(),
        'git_blob': git('rev-parse', f'{ref}:{path}').strip(),
        'snapshot_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'lines': len(source.splitlines()),
        'snapshot': str(destination),
    }
    return source

for ref in ['4c9804c', '046f034', '44b7c45', '26d8eab', 'b2505da']:
    for file in ['src/Baxy.App/UserMessagePolicy.cs',
                 'src/Baxy.App/ModelMessageComposer.cs',
                 'src/Baxy.Core/Operations/ProductOperationNarrator.cs',
                 'src/baxy_mind/llm.py']:
        snapshot(ref, file)
for ref in ['046f034', '26d8eab', 'b2505da']:
    snapshot(ref, 'src/Baxy.Kernel/Operations/OperationVisibleFacts.cs')
snapshot('26d8eab', 'scripts/goal06_voice_sample.py')
snapshot('046f034', 'tests/Baxy.Integration.Tests/CatalogNarrationCoverageTests.cs')
snapshot('44b7c45', 'artifacts/development/goal06_cien_respuestas.jsonl')
snapshot('44b7c45', 'artifacts/development/goal06_prosa_ab.json')
snapshot('b2505da', 'src/Baxy.App/PendingModelMessageQueue.cs')

project = Path(tempfile.mkdtemp(prefix='baxy-history-pure-'))
(project / 'Probe.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk">
<PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework>
<ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup>
</Project>''', encoding='utf-8')

stub = '''
internal sealed record MindTurnDecision(string Kind, string? Operation,
    IReadOnlyList<string> EffectOperations, bool PreserveObjective);
'''
for label, ref in [('Before', '4c9804c'), ('Change', '046f034'), ('After', '26d8eab')]:
    policy = git('show', f'{ref}:src/Baxy.App/UserMessagePolicy.cs')
    # Only the namespace is changed so both original policies can coexist.
    policy = policy.replace('namespace Baxy.App;', f'namespace Forensic.{label};')
    (project / f'{label}.cs').write_text(policy + stub, encoding='utf-8')

old = git('show', '4c9804c:src/Baxy.Core/Operations/ProductOperationNarrator.cs')
method = old[old.index('    private static string NarrateSystemTime('):
             old.index('    private static string NarrateProcessList(')]
(project / 'OldNarrator.cs').write_text('''using System.Globalization;
using System.Text.Json;
internal static class OldNarrator {
    public static string Run(JsonElement result) => NarrateSystemTime(new(result));
    private sealed record OperationOutcome(JsonElement? Result);
''' + method + '\n}', encoding='utf-8')

(project / 'Program.cs').write_text('''using System.Text.Json;
using Before = Forensic.Before.UserMessagePolicy;
using Change = Forensic.Change.UserMessagePolicy;
using After = Forensic.After.UserMessagePolicy;
var observed = JsonSerializer.Deserialize<JsonElement>("""
{"version":1,"utc":"2026-09-03T06:57:52.1829160+00:00","localUtcOffsetMinutes":-240}
""");
string oldText = OldNarrator.Run(observed);
string actualFacts = JsonSerializer.Serialize(new {
    kind="operation", operation="system.time", polarity="success",
    verified=true, succeeded=true, observed });
var probes = new {
    scope="Pure original narrator/policies; no LLM or product execution",
    oldNarrator=oldText,
    oldRequiredLiterals=Before.RequiredLiteralFacts(oldText),
    firstChangeRequiredLiterals=Change.RequiredLiteralFacts(actualFacts),
    newRequiredLiterals=After.RequiredLiteralFacts(actualFacts),
    oldRejection=Before.ModelResponseRejectionReason(oldText,
        Before.Create(oldText,Forensic.Before.UserMessageEvent.Status)),
    oldUnrelatedClockRejection=Before.ModelResponseRejectionReason("La hora es 14:30.",
        Before.Create(oldText,Forensic.Before.UserMessageEvent.Status)),
    firstChangeUnrelatedClockRejection=Change.ModelResponseRejectionReason("La hora es 14:30.",
        Change.Create(actualFacts,Forensic.Change.UserMessageEvent.Status)),
    newUnrelatedClockRejection=After.ModelResponseRejectionReason("La hora es 14:30.",
        After.Create(actualFacts,Forensic.After.UserMessageEvent.Status))
};
Console.WriteLine(JsonSerializer.Serialize(probes,new JsonSerializerOptions {WriteIndented=true}));
''', encoding='utf-8')

OUT.joinpath('manifest.json').write_text(json.dumps({
    'scope':'Read-only Git history; synthetic pure-code probes; no desktop effects',
    'project':str(project),'snapshots':snapshots}, ensure_ascii=False, indent=2),encoding='utf-8')
print(json.dumps({'project':str(project),'snapshot_count':len(snapshots)},ensure_ascii=False))
