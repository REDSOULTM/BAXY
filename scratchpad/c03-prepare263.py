"""Prepare the same desktop measurement with current source and request observations."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
snapshot=base/'astra-source263-snapshot'
snapshot.mkdir(exist_ok=False)
old=json.loads((base/'astra-source257-snapshot/FILES.json').read_text(encoding='utf-8'))
names=set(old)|{'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs',
 'tests/Baxy.Providers.Windows.Tests/WindowsInstalledApplicationOpenProviderTests.cs',
 'src/Baxy.Kernel/Operations/ProductCatalog.cs', 'src/baxy_mind/__main__.py',
 'src/baxy_mind/llm.py','src/baxy_mind/effect_intent.py','src/baxy_mind/planner.py',
 'src/baxy_mind/router.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/MindSidecarClient.cs',
 'src/Baxy.App/UserMessagePolicy.cs','src/Baxy.App/ModelMessageComposer.cs','main.py'}
hashes={}
for name in sorted(names):
    data=(root/name).read_bytes()
    hashes[name]=hashlib.sha256(data).hexdigest()
    dest=snapshot/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(data)
(snapshot/'FILES.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
hook=root/'scratchpad/c03-ui263-hook'
hook.mkdir(exist_ok=False)
source=(root/'scratchpad/c03-ui260-hook/sitecustomize.py').read_text(encoding='utf-8').replace('260','263')
source+='''
# Observe logical local HTTP requests without rewriting any payload or response.
from baxy_mind.llm import LlmRuntime
original_post = LlmRuntime._post
def observe_post(self, payload, *args, **kwargs):
    number = next(sequence)
    def write_wire(value):
        with lock, (PRIVATE / 'http-posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'time':time.monotonic(), 'pid':os.getpid(), 'id':number, **value}, ensure_ascii=False)+'\\n')
    write_wire({'stage':'request', 'payload':payload})
    try:
        response = original_post(self, payload, *args, **kwargs)
    except Exception as error:
        write_wire({'stage':'failure', 'errorType':type(error).__name__})
        raise
    write_wire({'stage':'response', 'response':response})
    return response
LlmRuntime._post = observe_post
'''
(hook/'sitecustomize.py').write_text(source,encoding='utf-8')
launcher=(root/'scratchpad/c03-launch260.py').read_text(encoding='utf-8').replace('260','263')
launcher=launcher.replace('astra-source257-snapshot','astra-source263-snapshot')
launcher=launcher.replace('source257','source262')
launcher=launcher.replace("['¿Qué hora es?','What time is it?','Explícame brevemente qué es la RAM.']",
 "['abre steam','Tengo en mente que abras steam','Si, abre steam','mhhhhh, porque no?, cuales son tus capacidades?']")
launcher=launcher.replace('All user input through desktop Computer Use.',
 'Input through desktop Computer Use or owner typing, record provenance. main.py determines the effective data profile; do not assume BAXY_DATA_DIR override survives it.')
launcher=launcher.replace('Read-only voice/Piper/AEC observers;',
 'Read-only voice/Piper/AEC and local logical HTTP observers;')
(root/'scratchpad/c03-launch263.py').write_text(launcher,encoding='utf-8')
print(json.dumps({'snapshotFiles':len(hashes),'launcher':'scratchpad/c03-launch263.py'}))
