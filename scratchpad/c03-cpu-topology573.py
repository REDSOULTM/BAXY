"""Test the missing physical-core observation, not another name for logical cores."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8')
source = source.replace('astra-native-compose-profile523', 'astra-cpu-topology573').replace('C03-native-compose-profile523-private', 'C03-cpu-topology573-private')
start = source.index('ids='); end = source.index('manifest=Path(', start)
source = source[:start] + '''
import ctypes,struct
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
topology=kernel.GetLogicalProcessorInformationEx
topology.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]
topology.restype=ctypes.c_int
def read_core_count():
    length=ctypes.c_uint32(0)
    assert topology(0,None,ctypes.byref(length))==0 and ctypes.get_last_error()==122
    assert 8<=length.value<=2**20
    storage=ctypes.create_string_buffer(length.value)
    assert topology(0,storage,ctypes.byref(length))!=0
    offset=count=0
    while offset<length.value:
        relationship,size=struct.unpack_from('<II',storage.raw,offset)
        assert relationship==0 and size>=8 and offset+size<=length.value
        count+=1;offset+=size
    assert offset==length.value and count>0
    return count,length.value
first=read_core_count();second=read_core_count();assert first==second
logical=kernel.GetActiveProcessorCount
logical.argtypes=[ctypes.c_uint16];logical.restype=ctypes.c_uint32
logical_count=logical(0xffff);assert 0<first[0]<=logical_count
write(out/'OBSERVED_TOPOLOGY.json',{'utc':datetime.now(timezone.utc).isoformat(),'physicalCoreCount':first[0],'logicalProcessorCount':logical_count,'bytes':first[1],'repeated_read_equal':True,'api':'GetLogicalProcessorInformationEx(RelationProcessorCore) and GetActiveProcessorCount(ALL_PROCESSOR_GROUPS)','source':'https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getlogicalprocessorinformationex'})
cases=json.loads((private.parent/'C03-native-cpu-owner558-private/cases.json').read_text(encoding='utf-8-sig'))
for case in cases:
    case['physicalCoreCount']=first[0];case['origin']='actual current topology added to consumed historical CPU capture; not one simultaneous product snapshot'
for index,template in enumerate(cases[:2]):
    case=copy.deepcopy(template);case['case']='counterfactual-topology-'+str(index)
    case['physicalCoreCount']=6;case['origin']='explicit synthetic6physical/8logical, changed processor label, not this machine'
    lines=case['payload']['messages'][1]['content'].splitlines()
    for i,line in enumerate(lines):
        if line.startswith('situation: '):
            facts=json.loads(line[11:]);facts['seen']['cpu'].update(logicalProcessorCount=8,model='Example Processor M12')
            lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
    case['payload']['messages'][1]['content']='\\n'.join(lines)
    cases.append(case)
assert len(cases)==6
''' + source[end:]
start = source.index('profiles='); end = source.index("write(private/'cases.json',cases)", start)
source = source[:start] + '''
profiles=[('baseline',{'seed':0}),('physical-topology',{'seed':0})]
def treatment(payload,case):
    lines=payload['messages'][1]['content'].splitlines()
    for i,line in enumerate(lines):
        if line.startswith('situation: '):
            facts=json.loads(line[11:]);facts['seen']['cpu']['physicalCoreCount']=case['physicalCoreCount']
            lines[i]='situation: '+json.dumps(facts,ensure_ascii=False)
    payload['messages'][1]['content']='\\n'.join(lines)
write(out/'PREREG.json',{'method':'Add one newly verified requested fact, physicalCoreCount, to four consumed current CPU writer captures. Preserve logical count, model and total CPU usage; no rename, unit conversion or instruction. Two synthetic topology controls change count relationship to6physical/8logical and model label to test beyond this Ryzen. Twelve native outputs across two arms.',
 'inheritance':'558/559 naming/instruction changes failed ownership and logical qualification. Current provider only exposes logical count; GetActiveProcessorCount cannot answer physical-core count. Today Win32_Processor independently reported8cores/16logical; the recorded diagnostic uses two consistent native RelationProcessorCore observations to verify the new fact before proposing a provider change.',
 'criteria':'Core-count requests should preserve both observed quantities with correct distinction and model; usage controls must not gain invented facts. Existing wrong first-person CPU attribution remains independently open and is not silently credited. Native success still requires real provider implementation, owner tests, integration and source gates. No production source, runtime or survey change here.',
 'sources':['https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getlogicalprocessorinformationex','src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProbe.cs:86','src/Baxy.Providers.Windows/SystemStatus/SystemStatusContracts.cs:26'],
 'server_command':command,'manifest_sha256':manifest_sha,'profiles':profiles,'case_count':len(cases),
 'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60}})
''' + source[end:]
source = source.replace("payload=copy.deepcopy(case['payload']);payload.update(settings)", "payload=copy.deepcopy(case['payload']);payload.update(settings)\n            if profile=='physical-topology':treatment(payload,case)")
source = source.replace('case_index%3', 'case_index%2')
source = source.replace('if gpu.peak_mib>3800:', 'if gpu.peak_mib is not None and gpu.peak_mib>3800:')
source = source.replace('if time.monotonic()-start>360:', "if gpu.peak_mib is None and time.monotonic()-start>10:violations.append('missing_gpu_telemetry')\n        if time.monotonic()-start>360:")
source = source.replace('27 native writer requests collected', '12 physical-topology writer requests collected')
exec(compile(source, __file__, 'exec'))
