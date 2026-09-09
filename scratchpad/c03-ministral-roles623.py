"""Preserve consecutive user contents in one model-compatible user turn."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-ministral-roles623').replace('C03-native-subject612-private','C03-ministral-roles623-private')
exec(compile(prefix,__file__,'exec'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
previous=private.parent/'C03-ministral622-private'
panel=[r for r in json.loads((previous/'panel.json').read_text(encoding='utf-8')) if r['task']=='prose']
assert len(panel)==12
for row in panel:
    original=copy.deepcopy(row['payload']['messages'])
    messages=[]
    for message in original:
        if messages and message['role']=='user' and messages[-1]['role']=='user':
            messages[-1]['content']+='\n\n'+message['content']
        else: messages.append(copy.deepcopy(message))
    assert '\n\n'.join(m['content'] for m in original)=='\n\n'.join(m['content'] for m in messages)
    row['original_messages']=original
    row['payload']['messages']=messages
    row['arm']='merged-consecutive-users'
write(private/'panel.json',panel)
command=json.loads((base/'astra-ministral622/PREREG.json').read_text(encoding='utf-8'))['command']
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
assert sha(command[command.index('-m')+1])=='9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8'
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':12,'calls':12,
    'method':'Same twelve frozen622 prose requests, model, backend, profile, budget and order. Join only adjacent user message contents with two newlines; all text, ordering, authors and policy remain, with no synthetic assistant response or deletion.612/618 supplied knowledge history-as-data as one user message followed by the current user request. Embedded Ministral template rejects that before decoding.',
    'inheritance':'Source77 already merges only the initial system prefix for Qwen3.5.622 actual HTTP500 and server Jinja exception demonstrate a separate consecutive-user restriction. Prior600 changed history representation for Qwen; this is an exact content-preserving role serialization repair for another model. No source adoption without product regression.',
    'criteria':'Separate template compatibility from semantic quality. Require all12 replies to finish naturally and preserve subject, truth, language and tone. Keep40 completed semantic622 results: a prose success cannot erase its classification failures or qualify global promotion.',
    'command':command,'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_llm_sha256':sha(root/'src/baxy_mind/llm.py'),
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('Collected40 native subject-attribution drafts','Collected12 role-compatible Ministral prose replies')
exec(compile(tail,__file__,'exec'))
