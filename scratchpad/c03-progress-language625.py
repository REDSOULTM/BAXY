"""Remove irrelevant mixed-language task metadata from progress-only requests."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-progress-language625').replace('C03-native-subject612-private','C03-progress-language625-private')
exec(compile(prefix,__file__,'exec'))
from baxy_mind.llm import MIXED_RESPONSE_LANGUAGE_POLICY
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
cases=json.loads((private.parent/'C03-progress-addressee565-private/cases.json').read_text(encoding='utf-8'))
assert len(cases)==8
es_contract='Idioma obligatorio: español. Fuera de los literales del contrato, no introduzcas palabras inglesas.'
mixed=[]
for case in cases:
    if not case['case'].startswith('es:'): continue
    row=copy.deepcopy(case);row['case']=row['case'].replace('es:','mixed:')
    assert row['payload']['messages'][-1]['content'].count(es_contract)==1
    row['payload']['messages'][-1]['content']=row['payload']['messages'][-1]['content'].replace(es_contract,MIXED_RESPONSE_LANGUAGE_POLICY)
    mixed.append(row)
cases+=mixed
panel=[]
for case in cases:
    for arm in ['original','language-only']:
        payload=copy.deepcopy(case['payload']);payload['seed']=0
        if arm=='language-only' and case['case'].startswith('mixed:'):
            payload['messages'][-1]['content']=payload['messages'][-1]['content'].replace(MIXED_RESPONSE_LANGUAGE_POLICY,es_contract)
        panel.append({'case_id':case['case'],'arm':arm,'payload':payload,
                      'criterion':'Brief natural first-person update, faithful phase and supplied step/count, no internal language analysis, invented measurements, completed effects, user instructions or ungrounded no-progress assertion.'})
write(private/'panel.json',panel)
command=json.loads((base/'astra-native-subject612/PREREG.json').read_text(encoding='utf-8'))['command']
assert sha(command[0])=='38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e'
assert sha(command[command.index('-m')+1])=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':12,'calls':24,
    'hypothesis':'Product605 emits a progress label narrating that the request mixes Spanish and English although the request itself is already excluded. The full mixed policy still describes the input and its lexical expectations. A progress-only writer needs the allowed output language, not that request-analysis metadata.',
    'method':'Reuse eight actual phase projections565 ES/EN; add the same four phases with current mixed-language policy. Compare only replacing mixed progress policy with the existing Spanish output-language contract, permitted by owner identity. Every system prompt, phase, step/count, sampler, model and budget remains. ES/EN packets are identical controls, not independent interventions. No source change, no requested goal inserted and no visible template.',
    'inheritance':'Current _compose_user_content already excludes original request for acting; do not reimplement that.565 changed third-person phase wording and was rejected, so phase wording is untouched.51/90/97 measured other narration/phase treatments;523 measured Qwen composer sampling, not this mixed-only metadata boundary. Use the registered greedy role to isolate payload structure, not claim optimality.',
    'criteria':'Read all24 outputs, retain every failure. Must remove mixed-language metanarration without losing truthful phase, step numbers or other languages; no source adoption from one improved sentence. Native only, no UI/voice or survey credit.',
    'command':command,'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_llm_sha256':sha(root/'src/baxy_mind/llm.py'),'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('Collected40 native subject-attribution drafts','Collected24 native progress-language outputs')
exec(compile(tail,__file__,'exec'))
