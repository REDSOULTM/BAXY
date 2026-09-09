"""Locate whether the native model or BAXY instructions cause the prose defects."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-ministral-layers624').replace('C03-native-subject612-private','C03-ministral-layers624-private')
exec(compile(prefix,__file__,'exec'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
previous=json.loads((private.parent/'C03-ministral-roles623-private/panel.json').read_text(encoding='utf-8'))
panel=[]
for row in previous:
    for arm in ['native','identity-only']:
        payload=copy.deepcopy(row['payload'])
        payload['messages']=[{'role':'user','content':row['text']}]
        if arm=='identity-only':
            payload['messages'].insert(0,{'role':'system','content':'Eres BAXY, un compañero que vive en el PC.'})
        panel.append({**row,'arm':arm,'payload':payload})
assert len(panel)==24
write(private/'panel.json',panel)
command=json.loads((base/'astra-ministral-roles623/PREREG.json').read_text(encoding='utf-8'))['command']
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
assert sha(command[command.index('-m')+1])=='9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8'
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':12,'arms':2,'calls':24,
    'method':'Native user-only versus one sentence of product identity. Same12 inputs623 and identical sampling/model/backend/context/token budget.623 full source606 prose packets already measured and retained, not regenerated. These variants localize instruction/context effects; they are not proposed production prompts and do not remove final-product requirements.',
    'hypothesis':'623 fixes the template exception but leaves language, tone, identity and response-to-gratitude defects. Test native comprehension before attributing them to the model globally; if user-only is correct, compare identity-only to the full BAXY layer already measured.',
    'criteria':'Read all drafts for actual requested meaning, subject, language and natural respectful tone. Native may identify its real model/assistant role; identity-only must identify BAXY. No fabricated performed effects or physical capabilities. No global promotion or survey credit from stripped prompts.',
    'command':command,'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_llm_sha256':sha(root/'src/baxy_mind/llm.py'),
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('Collected40 native subject-attribution drafts','Collected24 native/identity Ministral replies')
exec(compile(tail,__file__,'exec'))
