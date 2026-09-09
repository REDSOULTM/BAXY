"""Original Gemma E2B in the new subject-attribution task, with its own profile."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-native-subject612.py').read_text(encoding='utf-8')
prefix = source[:source.index('manifest = ')]
prefix = prefix.replace('astra-native-subject612', 'astra-gemma-subject613')
prefix = prefix.replace('C03-native-subject612-private', 'C03-gemma-subject613-private')
exec(compile(prefix, __file__, 'exec'))

manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_sha = sha(manifest)
assert manifest_sha == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
original = json.loads((base / 'astra-gemma-original497/PREREG.json').read_text(encoding='utf-8'))
assert sha(original['model']) == original['model_sha256']
assert sha(original['server']) == original['server_sha256']
previous = json.loads((private.parent / 'C03-native-subject612-private/panel.json').read_text(encoding='utf-8'))
panel = []
for row in previous:
    if row['arm'] not in {'native', 'history'}:
        continue
    for thinking in [False, True]:
        payload = copy.deepcopy(row['payload'])
        payload.update(temperature=1.0, top_p=.95, top_k=64, min_p=0.0,
                       presence_penalty=0.0, repeat_penalty=1.0,
                       max_tokens=3072, reasoning_budget_tokens=-1, verbose=True)
        payload['chat_template_kwargs'] = {'enable_thinking':thinking}
        panel.append({**row, 'arm':row['arm'] + ('-thinking' if thinking else '-direct'),
                      'payload':payload})
assert len(panel) == 32
write(private / 'panel.json', panel)
command = json.loads((private.parent / 'C03-gemma-original497-private/effective-server-command.json').read_text(encoding='utf-8'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0))
    port = sock.getsockname()[1]
command[command.index('--port')+1] = str(port)
command[command.index('--log-file')+1] = str(private / 'server.log')
assert command[0] == original['server'] and command[command.index('-m')+1] == original['model']
write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(),'cases':8,'arms':4,'calls':32,
    'method':'Gemma4-E2B-it original Q4_K_M, original497 hashes and measured lazy-on b10809 native template. Same eight subject-attribution inputs612, with native-only versus complete conversation policies and welcome history; each tested with thinking off/on under the documented Google sampling profile. No forced grammar/JSON, tools, guards, retries, providers or product source changes. Native identity can be Gemma; with BAXY identity supplied the product role is required.3072tokens headroom in both modes; record cuts honestly.',
    'hypothesis':'Qwen612 misreads the colloquial identity question even without BAXY. Test whether a lighter already-qualified alternative understands that language/subject boundary before proposing any model change.497 measured tool arguments, not this population or free prose. Its polarity/interface failures remain open and would block global promotion; success here alone cannot replace the registered model.',
    'criteria':'All eight cases must preserve speaker/addressee, appropriate language and truthful natural answers in each proposed profile. Do not select only a favorable draft or erase H0012 failures. Thinking/non-thinking comparison holds all other Gemma settings and messages fixed. This is a profile-qualified candidate comparison, not a weights-only comparison with Qwen.',
    'research_checked_20260909':['https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4','https://ai.google.dev/gemma/docs/capabilities/thinking','https://huggingface.co/google/gemma-4-E2B-it/blob/main/generation_config.json'],
    'research_reused':'Gemma4 technical report2607.02770, source/template/runtime audits448–497, lazy-mode memory measurement462/464/473. Official generation_config givesT1/top_p.95/top_k64; min_p0 avoids the extra llama default filter. Thinking is a conversation-level boolean. New comparison concerns colloquial prose; no MTP, multimodal encoder or system-prompt sweep.',
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':original['model_sha256'],
    'server_sha256':original['server_sha256'],'panel_sha256':sha(private / 'panel.json'),
    'source_sha256':sha(root / 'src/baxy_mind/llm.py'),'source_modified':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240,'request_seconds':90},
})
tail = source[source.index("log = (private / 'launch.log')"):]
tail = tail.replace('urlopen(request,timeout=30)', 'urlopen(request,timeout=90)')
tail = tail.replace('Collected40 native subject-attribution drafts', 'Collected32 Gemma subject-attribution drafts')
exec(compile(tail, __file__, 'exec'))
