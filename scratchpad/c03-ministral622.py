"""Profile-qualified alternative on the observed subject and semantic boundaries."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-ministral622').replace('C03-native-subject612-private','C03-ministral622-private')
exec(compile(prefix,__file__,'exec'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
old=json.loads((base/'astra-native-ministral/PREREGISTRO.json').read_text(encoding='utf-8'))
model=old['manifest']['gguf']
assert sha(model)=='9ed150d4367e68df0ac8e1540f6ddc65b42d0ee26378329d1ecbca60f93fc5f8'
panel=json.loads((private.parent/'C03-social-kind615-private/panel.json').read_text(encoding='utf-8'))
for row in panel:
    row['task']='semantic_guard'
prose=json.loads((private.parent/'C03-style618-private/panel.json').read_text(encoding='utf-8'))
panel += [{**r,'task':'prose','arm':'source606'} for r in prose if r['arm']=='original']
assert len(panel)==52
for row in panel:
    payload=row['payload']
    payload.update(temperature=.05,top_p=.95,top_k=0,min_p=0.0,presence_penalty=0.0,
                   frequency_penalty=0.0,repeat_penalty=1.0,max_tokens=512,seed=0)
    payload['chat_template_kwargs']={'enable_thinking':False}
    payload.pop('reasoning_budget_tokens',None)
write(private/'panel.json',panel)
command=json.loads((base/'astra-native-subject612/PREREG.json').read_text(encoding='utf-8'))['command']
command[0]='D:/BAXYRuntime/assets/llama-v0.4.0-b10809-cuda12.4/llama-server.exe'
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
command[command.index('-m')+1]=model
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
write(out/'PREREG.json',{
    'utc':datetime.now(timezone.utc).isoformat(),'cases':32,'calls':52,
    'method':'Twenty semantic615 inputs, original and social-subtype definitions/grammars unchanged, plus12 identity/gratitude prose controls618 using the original source606 style. Native Ministral3-3B-Instruct2512 Q4, no BAXY classification, retries or final guards.512tokens each to distinguish cuts. Capture all native responses; no source edits or model promotion.',
    'inheritance':'REGISTRO_DE_MANTENIBILIDAD1022 rejected Ministral on July performance/VRAM. Existing astra-native-ministral used old composition scaffolding on arithmetic/knowledge and different b9980. Those results remain; none directly tests current subject/social boundaries.622 is a model/profile comparison, not an isolated weights-only experiment or a reason to repeat failed semantic prompt sweeps.',
    'profile':'Official card checked2026-09-09 recommends temperature below0.1 for production. Reuse measured Ministral T.05/top_p.95; explicitly disable extra top_k/min_p and repetition penalties to avoid importing Qwen/Gemma filtering. Only temperature bound is manufacturer recommendation; other settings are a declared candidate profile, not proven optimum. Non-reasoning Instruct; no vision encoder. Native embedded template and verified b10809 backend;3slots4096 each, KVq8 as prior baseline.',
    'sources':['https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF#recommended-settings','https://arxiv.org/abs/2601.08584'],
    'criteria':'Judge every raw type/count against frozen615 labels, separately recording no-effect normalization; all12 prose replies must preserve subject, language and warm truthful tone. No native result grants survey credit. An alternative must outperform relevant failures without new regressions before integration; keep latency/resource costs and prior rejections visible.',
    'command':command,'model_sha256':sha(model),'server_sha256':sha(command[0]),
    'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_llm_sha256':sha(root/'src/baxy_mind/llm.py'),
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240}})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('Collected40 native subject-attribution drafts','Collected52 native Ministral boundary responses')
exec(compile(tail,__file__,'exec'))
