"""Test retaining the social subtype in the existing semantic guard, without code changes."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-social-kind615').replace('C03-native-subject612-private','C03-social-kind615-private')
exec(compile(prefix,__file__,'exec'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
prior=private.parent/'C03-gemma-product614-private'
with (prior/'http-posts.jsonl').open(encoding='utf-8-sig') as stream:
    original=next(row['payload'] for row in map(json.loads,stream) if row.get('stage')=='request' and row['id']==95)
old='request_type es stable_conversation para charla, reacciones o conocimiento estable contestable sin consultar fuentes ni estado;'
new=('request_type es social_conversation para un saludo, agradecimiento, presentación personal o reacción conversacional que no pide información, impone restricciones ni solicita efectos; '
     'stable_conversation para conocimiento estable, explicaciones, contenido redactado en el chat o restricciones sin efecto que puedan responderse sin consultar fuentes ni estado; '
     'un saludo junto a una petición no convierte esa petición en social;')
assert original['messages'][0]['content'].count(old)==1
candidate=copy.deepcopy(original)
candidate['messages'][0]['content']=candidate['messages'][0]['content'].replace(old,new).replace('para stable_conversation su valor','para stable_conversation y social_conversation su valor')
candidate['grammar']=candidate['grammar'].replace('request-type ::= ','request-type ::= '+json.dumps(json.dumps('social_conversation'))+' | ',1)
cases=[
    ('H0032','Bien, bien.','social_conversation','zero'),
    ('H0218','Muy bien gracias','social_conversation','zero'),
    ('social-es','Me alegra que lo hayas entendido.','social_conversation','zero'),
    ('social-en','Doing well, how about you?','social_conversation','zero'),
    ('greeting-info','Hola, explícame por qué llueve.','stable_conversation','zero'),
    ('knowledge-en','Tell me something odd about thunder.','stable_conversation','zero'),
    ('H0012','to quien chuta eres.','stable_conversation','zero'),
    ('self-introduction','Me llamo Vera.','social_conversation','zero'),
    ('negative-constraint','No abras ninguna ventana.','stable_conversation','zero'),
    ('missing-app','Abre una aplicación.','incomplete_effect','one'),
    ('missing-volume','Pon el volumen a...','incomplete_effect','one'),
    ('missing-reference-en','Please send it.','incomplete_effect','one'),
    ('physical-action','Regá las plantas.','environment_change','one'),
    ('live-cpu-en',"What is my computer's CPU usage?",'external_read','one'),
    ('open-app','Abre Steam.','environment_change','one'),
    ('compound','Abre Steam y sube el volumen al 40%.','environment_change','multiple'),
    ('knowledge-imperative','Enumera tres ejemplos de mamíferos.','stable_conversation','zero'),
    ('draft-chat','Escribe un saludo en el chat.','stable_conversation','zero'),
    ('named-source','Resume el archivo presupuesto.txt.','external_read','one'),
    ('greeting-action','Hola, abre Steam.','environment_change','one'),
]
panel=[]
for case_id,text,expected,count in cases:
    for arm,base_payload in [('original',original),('social-subtype',candidate)]:
        payload=copy.deepcopy(base_payload)
        payload['messages'][-1]['content']='Mensaje actual:\n'+text
        label='stable_conversation' if arm=='original' and expected=='social_conversation' else expected
        panel.append({'case_id':case_id,'text':text,'arm':arm,'expected_type':label,'expected_count':count,'payload':payload})
write(private/'panel.json',panel)
command=json.loads((prior/'effective-server-command.json').read_text(encoding='utf-8'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
assert sha(command[command.index('-m')+1])=='740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8'
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
write(out/'PREREG.json',{
    'utc':datetime.now(timezone.utc).isoformat(),'cases':20,'arms':2,'calls':40,
    'hypothesis':'The native no-tool branch defaults to knowledge.614 guard95 already knows H0032 is stable conversation, but the representation erases the social subtype; main rejects a normal conversational question as an unanswered explanation. Test a subtype in the existing guard, rather than adding a phrase alias, another classifier call, or relaxing the information-answer contract.',
    'method':'Exact native614 semantic guard payload/profile/backend with one representation change: add social_conversation to the request_type grammar and distinguish that subtype in its instruction. All other effect labels/counts, sampler, token budget, template and no-thinking profile unchanged.20 preregistered contrasts; old social labels fold to stable_conversation only for baseline scoring. No product source, returned decisions, or output rewriting.',
    'criteria':'Correct type/count, especially social versus information, imperatives, constraints, named-source reads, missing arguments and actions. Any proposed subtype must never select operations or grant effect authority. No source adoption from merely rescuing H0032; compare all20 including baseline failures. Existing no-effect normalization and question-answer guards must survive an eventual integration.',
    'research_reused':'Current Gemma613 official prompt/generation docs and native614 trace. This is a causal classification comparison using the existing greedy role, not a claim that greedy is globally optimal for Gemma. Already-qualified direct prose profile613 is a different role. Native grammar constrains syntax, not semantic correctness.',
    'command':command,'model_sha256':sha(command[command.index('-m')+1]),'server_sha256':sha(command[0]),
    'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_main_sha256':sha(root/'src/baxy_mind/__main__.py'),
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('Collected40 native subject-attribution drafts','Collected40 native social-subtype classifications')
exec(compile(tail,__file__,'exec'))
