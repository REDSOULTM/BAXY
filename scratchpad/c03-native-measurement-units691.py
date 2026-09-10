"""Compare binary/decimal quantity units on the exact thirty numeric fixtures690."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index("history = [{'role'")]
prefix=prefix.replace('astra-native-subject612','astra-native-measurement-units691').replace('C03-native-subject612-private','C03-native-measurement-units691-private')
exec(compile(prefix,__file__,'exec'))
helper=(root/'scratchpad/c03-native-measurements690.py').read_text(encoding='utf-8')
helper=helper[helper.index('def quantity('):helper.index('class Captured(')]
assert helper.count("unit='GiB'")==1 and helper.count("value/(2**30) if unit=='GiB'")==1
helper=helper.replace("unit='GiB'","unit='GB'").replace("value/(2**30) if unit=='GiB'","value/(10**9) if unit=='GB'")
exec(compile(helper,__file__,'exec'))
previous=json.loads((private.parent/'C03-native-measurements690-private/panel.json').read_text(encoding='utf-8'))
original={r['case_id']:r for r in previous if r['arm']=='current_bytes'}
panel=[]
for row in previous:
    if row['arm']!='typed_quantities':continue
    current=copy.deepcopy(row)
    current['arm']='binary_quantities'
    decimal=copy.deepcopy(row)
    decimal['arm']='decimal_quantities'
    count=0
    for message in decimal['payload']['messages']:
        if message['role']!='user' or 'situation: ' not in message['content']:continue
        before,rest=message['content'].split('situation: ',1)
        _,end=json.JSONDecoder().raw_decode(rest)
        facts=project_quantities(original[row['case_id']]['projected'])
        message['content']=before+'situation: '+json.dumps(facts,ensure_ascii=False)+rest[end:]
        count+=1
    assert count==1
    panel.extend([current,decimal])
assert len(panel)==60 and psutil.virtual_memory().available>=1800*2**20
write(private/'panel.json',panel)
runner=source[source.index('command = json.loads'):]
start=runner.index("write(out / 'PREREG.json', {");end=runner.index("log = (private / 'launch.log')",start)
runner=runner[:start]+'''write(out/'PREREG.json',{
    'utc':datetime.now(timezone.utc).isoformat(),'cases':30,'arms':2,'calls':60,
    'method':'Exact thirty fixtures690. Binary arm reuses each complete typed690 request. Decimal arm changes only quantity division from2**30/GiB to10**9/GB; percentages and all other fields/messages/settings unchanged. Native first drafts only, no validators/retries/source modification. Verify binary controls reproduce690.',
    'criteria':'Truthful quantity values and unit labels, correct total/available/used/dedicated/shared/engine meaning, unknowns preserved, requested completeness and language. Decimal conversion cannot substitute installed RAM for measured usable RAM. Evaluate every case and any regressions.',
    'inheritance':'690 fixed several arithmetic/VRAM mistakes but some GiB values were mislabeled gigabytes or GB. This is a single representation comparison within the same full numeric category, not per-literal tuning. Microsoft distinguishes physically installed RAM from GlobalMemoryStatusEx usable RAM.',
    'sources':['https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getphysicallyinstalledsystemmemory'],
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),'server_sha256':sha(command[0]),
    'source_sha256':sha(root/'src/baxy_mind/llm.py'),'panel_sha256':sha(private/'panel.json'),
    'source_modified':False,'source_adopted':False,'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
''' +runner[end:]
runner=runner.replace('Collected40 native subject-attribution drafts; adjudication pending.','Collected60 paired unit drafts; adjudication pending.')
exec(compile(runner,__file__,'exec'))
