"""Remove forced decoding to measure actual native thinking, not its option flag."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix=source[:source.index('manifest = ')]
prefix=prefix.replace('astra-native-subject612','astra-native-schema617').replace('C03-native-subject612-private','C03-native-schema617-private')
exec(compile(prefix,__file__,'exec'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest_sha=sha(manifest)
assert manifest_sha=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
previous=private.parent/'C03-social-thinking616-private'
panel=json.loads((previous/'panel.json').read_text(encoding='utf-8'))
for row in panel:
    del row['payload']['grammar']
    row['payload']['messages'][0]['content'] += ('\nLa respuesta final debe ser un objeto JSON con exactamente dos claves: '
        'request_type y effect_count. Usa uno de los tipos y uno de los conteos definidos arriba, sin claves adicionales.')
write(private/'panel.json',panel)
command=json.loads((base/'astra-social-thinking616/PREREG.json').read_text(encoding='utf-8'))['command']
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
command[command.index('--log-file')+1]=str(private/'server.log')
assert sha(command[0])=='cb29f66008d4d73cce17cab2c2569ab318eb244b0b2ca2a15024b44d90dfcd3f'
assert sha(command[command.index('-m')+1])=='740185b21d22ceb83a11c3aa62ad5842ef32c70f6096d756bbee85a1e4ec34b8'
write(out/'PREREG.json',{
    'utc':datetime.now(timezone.utc).isoformat(),'cases':20,'arms':2,'calls':40,
    'method':'Same616 cases, semantic definitions, Google profile and3072-token budget. Replace forced grammar with explicit final JSON serialization instruction, without changing labels or examples. Direct/thinking arms differ only in enable_thinking. Native responses are retained exactly; malformed JSON, extra text, cuts and absent thoughts count explicitly. No product adoption, repair hook or label rewriting.',
    'hypothesis':'616 produced zero actual reasoning_content even with20 enable_thinking=true requests. Its result does not establish thinking quality. Native613 already demonstrated real thinking with this model/backend. Isolate forced decoding before concluding a model comprehension failure; do not iterate the semantic prompt.',
    'criteria':'Read all outputs. Strict JSON and exact two keys required; types and normalized count as615. Report raw count errors too. If no actual thinking emerges, stop this comparison as technically invalid. If native succeeds but constrained fails, investigate compatible structured decoding instead of retaining unconstrained output without validation. No survey credit.',
    'command':command,'manifest_sha256':manifest_sha,'panel_sha256':sha(private/'panel.json'),
    'source_main_sha256':sha(root/'src/baxy_mind/__main__.py'),'source_llm_sha256':sha(root/'src/baxy_mind/llm.py'),
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':360,'request_seconds':90},
})
tail=source[source.index("log = (private / 'launch.log')"):]
tail=tail.replace('> 240','> 360').replace('urlopen(request,timeout=30)','urlopen(request,timeout=90)')
tail=tail.replace('Collected40 native subject-attribution drafts','Collected40 native JSON classifications')
exec(compile(tail,__file__,'exec'))
