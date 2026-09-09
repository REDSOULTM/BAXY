"""Compare precise Windows-account scope in an actual native request, no effects."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import unicodedata

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.llm import LlmRuntime

out = root / 'artifacts/comprobaciones/C03/astra-identity-scope387'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-identity-scope387-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
wire = private.parent / 'C03-native-generalization386-private/http-posts.jsonl'
def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower().strip('¿? .')
reference = next(row['payload'] for row in map(json.loads, wire.open(encoding='utf-8-sig'))
    if row.get('stage') == 'request' and len(row['payload'].get('tools', [])) > 4
    and norm(row['payload']['messages'][-1].get('content', '')) == 'quien soy')
function = next(t['function'] for t in reference['tools'] if t['function']['name'] == 'baxy_system__identity')
replacement = 'Lee la cuenta de Windows bajo la que se ejecuta BAXY: su dominio y nombre de usuario, mediante dos observaciones coherentes. No identifica a la persona ni recupera su nombre dicho en conversación.'
cases = [{'id': 'actual-human-es', 'text': reference['messages'][-1]['content'], 'expected': 'Answer Eva from the human declaration; no operation.'},
    {'id': 'human-en', 'text': 'Who am I?', 'expected': 'Answer Eva from the same human declaration; no operation.'},
    {'id': 'account-es', 'text': '¿Con qué cuenta de Windows estás ejecutándote?', 'expected': 'Select system.identity; do not infer the OS account from Eva.'},
    {'id': 'account-en', 'text': 'Which Windows account are you running under?', 'expected': 'Select system.identity; do not infer the OS account from Eva.'}]
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-native-generalization386/PREREG.json').read_text(encoding='utf-8'))
model = Path(prior['model'])
assert sha(model) == prior['model_sha256']
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases, 'reference': reference,
    'method': 'Actual386 native primary payload for human-identity-es. Four controls keep that history, shortlist and request configuration; only the last request text differs across cases. For each case compare original system.identity description versus precise Windows-account scope. No prompt, sampler, model, history or production-source changes, no effect or plan execution. First case is the actual386 request; other three are explicitly synthetic controls. Not full mind, App, UI, voice or fresh-human acceptance.',
    'reason': '386 primary chooses the Windows process account despite human Eva in context, and all later stages preserve it. ProductCatalog1272 already reads only Windows domain/username; make that existing capability boundary unambiguous in its description. No new capability, name list or veto. Inherits typed catalog and the native tool mechanism already researched in INVESTIGACION_MODELO_C03 and381/382.',
    'old_description': function['description'], 'new_description': replacement,
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest),
    'backend_sha256': sha(config['llama_server']), 'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
client = LlmRuntime()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    (out / 'command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
    for case in cases:
        for variant in ['baseline', 'windows-account-scope']:
            payload = copy.deepcopy(reference)
            payload['messages'][-1]['content'] = case['text']
            if variant != 'baseline':
                next(t['function'] for t in payload['tools'] if t['function']['name'] == function['name'])['description'] = replacement
            if case['id'] == 'actual-human-es' and variant == 'baseline':
                assert payload == reference
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': case['id'], 'variant': variant, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            result = {'id': case['id'], 'variant': variant, 'choice': response['choices'][0]}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
finally:
    client.close()
assert sha(manifest) == prereg['manifest_sha256']
