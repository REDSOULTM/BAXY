from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-read-candidates414'
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8')]
assert len(rows) == 30
report = '''# 414 — filtro read_only antes del top4:14/15→14/15, rechazado

Mismos casos e historia exacta413. Early-read conserva target frío pero recita el
caliente; filtrar candidatos read_only antes del top4 corrige el caliente y vuelve
a aclarar el frío. Cambia qué caso falla, no mejora el conjunto. Los13controles
restantes se conservan. No adoptar ni combinar por modo frío/caliente, ni añadir
otro pase idéntico o una lista de frases. Se cambia de estrategia/línea de bloqueo.

Quince consultas por brazo,30respuestas; las primarias frías de cada brazo igualan
411 con aserción desde el offset propio del archivo. Source410 intacta, sin efectos,
promoción, UI/voz, recursos nuevos ni aceptación fresca. Modelos cerrados.413 y414
quedan como diagnósticos parciales; ninguna recuperación temprana está en producto.

Siguiente bloqueo415: prosa de Windows11 confundido con versiónNT10.0 en411T5.
El proveedor RtlGetVersion sólo transporta números y arquitectura. CIM local ya
observó el nombre real. Se medirá composición con el dato Caption antes de añadir
lectura nueva: misma petición/payload base411, sólo un campo observado adicional.
No se inyecta una respuesta ni se fija Windows11 en producto.
'''
(out / 'RESULT.md').write_text(report, encoding='utf-8')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
private = Path(prereg['private'])
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.jsonl', 'EXIT.json', 'payload-match-early-read.json', 'payload-match-read-only-candidates.json']]
paths += [private / n for n in ['http-posts.jsonl', 'turn-audit.jsonl', 'hook/sitecustomize.py']]
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')

source = (root / 'scratchpad/c03-required-fact401.py').read_text(encoding='utf-8')
source = source.replace('astra-required-fact401', 'astra-os-caption415').replace('C03-required-fact401-private', 'C03-os-caption415-private')
begin = source.index('source = private.parent')
end = source.index('\ndef sha(', begin)
builder = '''source = private.parent / 'C03-account-product411-private'
audit = [json.loads(line) for line in (source / 'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(line) for line in (source / 'http-posts.jsonl').open(encoding='utf-8-sig')]
row = next(r for r in audit if r['trace'] == 't5' and r['stage'] == 'first')
payload = next(r['payload'] for r in wire if r.get('stage') == 'request'
               and 'majorVersion' in r['payload']['messages'][-1].get('content', '')
               and r['payload']['messages'][-1]['content'].startswith('Which Windows version am I running?'))
observed = json.loads((root / 'artifacts/comprobaciones/C03/astra-account-product411/OS_OBSERVATION.json').read_text(encoding='utf-8'))
actual = {'id': 'actual411-windows11-en', 'request': payload['messages'][-1]['content'].split('\\nsituation:')[0],
          'situation': json.loads(row['situation']), 'reference': payload,
          'origin': 'actual411/t5 and independent local CIM OS_OBSERVATION', 'caption': observed['caption'],
          'expected': 'Report Windows11 Home Single Language, not Windows10 inferred from NTmajor10; keep the observed build if mentioned.'}
cases = [actual]
for identifier, request, caption, build, workstation in [
    ('windows11-es', '¿Qué versión de Windows tengo?', observed['caption'], 26200, True),
    ('windows10-en', 'Which version of Windows is this?', 'Microsoft Windows 10 Enterprise', 19045, True),
    ('server2022-es', '¿Qué Windows tiene este servidor?', 'Microsoft Windows Server 2022 Standard', 20348, False),
]:
    case = copy.deepcopy(actual)
    case.pop('reference')
    case.update(id=identifier, request=request, caption=caption,
                origin='synthetic development OS snapshot/request; not a measurement of this PC',
                expected='Report the supplied OS caption without converting NTmajor10 into a marketing release.')
    case['situation']['observed']['os'].update(buildNumber=build, isWorkstation=workstation)
    cases.append(case)
'''
source = source[:begin] + builder + source[end:]
begin = source.index('def facts(')
end = source.index('\nfor key in list(os.environ)', begin)
source = source[:begin] + '''def facts(case, variant):
    situation = copy.deepcopy(case['situation'])
    if variant == 'caption':
        situation['observed']['os']['caption'] = case['caption']
    return {'situation': json.dumps(situation, ensure_ascii=False)}

''' + source[end:]
source = source.replace('for case in cases[:2]:', "for case in [c for c in cases if 'reference' in c]:")
source = source.replace("['baseline', 'retain-value']", "['baseline', 'caption']")
source = source.replace('captured393b', 'captured411')
fields = {
    'method': 'Four guarded compose_user_message cases; baseline versus only observed.os.caption. Actual411T5 baseline must equal its captured native payload offline and live. Caption for actual case is independently observed via local CIM; remaining ES/Windows10/Server2022 cases are explicitly synthetic controls. Same prompt/model/sampler/guards, no response injection, source change, extra tool role, product effect or promotion. Measure whether conveying the existing Windows caption prevents marketing-version hallucination before adding a provider read.',
    'inheritance': 'biblioteca/carter/carter_v5/microagents/windows_commands.md:23-32 uses Windows system commands but does not solve OS marketing naming. Current WindowsSystemStatusProbe.ReadOperatingSystem169 uses RtlGetVersion numbers only. Current ExternalProcessRunner and DeviceControlAdapter already bound local PowerShell/CIM; reuse if needed, no new dependency or copied obsolete WMIC. Primary Microsoft OSVERSIONINFOEXW table lists Windows10 and11 both10.0; Win32_OperatingSystem.Caption is the observed OS description.411 CIM independently confirmed Windows11, version10.0.26200.',
    'criteria': 'All four outputs identify the supplied actual/synthetic OS release and edition without misreading NTversion as marketingversion. Do not count a literal match alone, a blank reply or a technical payload dump as useful. No provider implementation before this compositional comparison and real CIM mechanism are understood.'}
lines = []
for line in source.splitlines():
    key = next((key for key in fields if line.startswith('    '+repr(key)+':')), None)
    lines.append('    '+repr(key)+': '+repr(fields[key])+',' if key else line)
source = '\n'.join(lines) + '\n'
source = source.replace("'criteria':", "'sources': ['https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ns-wdm-_osversioninfoexw', 'https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem'],\n    'criteria':", 1)
target = root / 'scratchpad/c03-os-caption415.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
print('414 recorded/rejected;415 prepared, no source changes')
