"""Capture and explicitly set adapter state after560 preflight stopped before inference."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-inherited-lora560.py').read_text(encoding='utf-8')
source=source.replace('astra-inherited-lora560','astra-inherited-lora561').replace('C03-inherited-lora560-private','C03-inherited-lora561-private')
old=r"    assert len(adapters)==1 and adapters[0]['id']==0 and adapters[0]['scale']==0\n    write(out/'ADAPTERS.json',adapters)"
new=r"    write(out/'INITIAL_ADAPTERS.json',adapters)\n    assert len(adapters)==1 and adapters[0]['id']==0\n    request=urllib.request.Request(url+'/lora-adapters',data=json.dumps([{'id':0,'scale':0.}]).encode(),headers={'Content-Type':'application/json'})\n    with urllib.request.urlopen(request,timeout=5) as response:write(out/'SET_ADAPTERS.json',json.load(response))\n    with urllib.request.urlopen(url+'/lora-adapters',timeout=5) as response:adapters=json.load(response)\n    write(out/'ADAPTERS.json',adapters)\n    assert len(adapters)==1 and adapters[0]['id']==0 and adapters[0]['scale']==0"
assert old in source
source=source.replace(old,new)
source=source.replace('Adapter loaded once with zero default;', '560 stopped before inference because its initial-state assertion failed; no adapter state response was saved there, so do not infer which field differed.561 saves the response, explicitly sets global scale0 via documented loopback API and reads it back before inference. Adapter loaded once with zero verified default;')
exec(compile(source,__file__,'exec'))
