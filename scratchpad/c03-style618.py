"""Clarify masculine self-reference and informal address without literal filters."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-style618').replace('C03-native-subject612-private','C03-style618-private')
prefix=prefix.replace('out.mkdir(exist_ok=False)', "out.mkdir(exist_ok=True)\nassert not (out/'PREREG.json').exists()")
prefix=prefix.replace('private.mkdir(exist_ok=False)', "private.mkdir(exist_ok=True)\nassert not (private/'panel.json').exists()")
exec(compile(prefix,__file__,'exec'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
prior=private.parent/'C03-gemma-product614-private'
with (prior/'http-posts.jsonl').open(encoding='utf-8-sig') as stream:
    social=next(r['payload'] for r in map(json.loads,stream) if r.get('stage')=='request' and r['id']==76)
previous=json.loads((private.parent/'C03-gemma-subject613-private/panel.json').read_text(encoding='utf-8'))
cases=[r for r in previous if r['arm']=='history-direct']
for case_id,text,lang in [('H0218','Muy bien gracias','es'),('thanks-es','Te agradezco la ayuda.','es'),
                          ('thanks-en','Thank you for your help.','en'),('thanks-mixed','Muchas gracias, that helped.','mixed')]:
    payload=copy.deepcopy(social)
    assert payload['messages'][-1]=={'role':'user','content':'Muy bien gracias'}
    payload['messages'][-1]['content']=text
    if lang=='en':
        payload['messages'][0]['content']=payload['messages'][0]['content'].replace('responde exclusivamente en español.','responde exclusivamente en inglés.')
    cases.append({'case_id':case_id,'text':text,'criterion':'Natural acknowledgement without projecting a style word, invented fact or effect; appropriate requested language.', 'payload':payload})
panel=[]
old='Eres un él. Tuteas.'
new='Habla de ti en masculino y dirígete al usuario de tú.'
for case in cases:
    for arm in ['original','explicit-style']:
        payload=copy.deepcopy(case['payload'])
        assert payload['messages'][0]['content'].count(old)==1
        if arm=='explicit-style':
            payload['messages'][0]['content']=payload['messages'][0]['content'].replace(old,new)
        # Same complete-first-draft headroom and sampling for both arms.
        payload.update(temperature=1.0,top_p=.95,top_k=64,min_p=0.0,presence_penalty=0.0,
                       repeat_penalty=1.0,max_tokens=512,seed=0)
        payload['chat_template_kwargs']={'enable_thinking':False}
        panel.append({**case,'arm':arm,'payload':payload})
assert len(panel)==24
write(private/'panel.json',panel)
command=json.loads((prior/'effective-server-command.json').read_text(encoding='utf-8'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
assert sha(command[command.index('-m')+1])=='740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8'
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':12,'arms':2,
    'hypothesis':'Actual614 H0218 first draft addresses the user as tuteo;613 thinking also projected Soy él. Clarify the subject of gender/address instructions while preserving product identity. This is separate from the rejected social classifier615–617.',
    'method':'Eight identity/subject controls613 plus actual H0218 chat payload614 and three ES/EN/mixed gratitude variants. Native direct Gemma documented profile in both arms. Replace only Eres un él. Tuteas. with a grammatical imperative expressing the same identity. No blocked-word lists, literal responses, role overrides or source changes.512-token headroom equal in both arms; not exact full-product replay.',
    'criteria':'All12 natural, truthful and appropriately localized replies; no subject/style leakage, vocative confusion or loss of identity. Record all changes and failures. Require product regression before any adoption; no survey credit.',
    'command':command,'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_llm_sha256':sha(root/'src/baxy_mind/llm.py'),'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('Collected40 native subject-attribution drafts','Collected24 native style drafts')
exec(compile(tail,__file__,'exec'))
