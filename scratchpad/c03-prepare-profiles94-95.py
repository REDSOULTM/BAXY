from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-thinking93.py').read_text(encoding='utf-8')
source = source.replace('import time\n', 'import time\nimport urllib.request\n')
source = source.replace("'astra-progress-thinking93'", "'astra-progress-thinking94'")
source = source.replace("cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]",
    "cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()][:1]")
source = source.replace('response = client._post(payload)', '''request = urllib.request.Request(client._endpoint + '/v1/chat/completions',
                    data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=120) as stream:
                    response = json.load(stream)''')
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Single first93 case to diagnose censoring, not a six-case acceptance or progress candidate. '
    '93 began a90s outer request but _effective_request_timeout capped each HTTP attempt at the default19s '
    'and _post allowed2 attempts, so no final was observed. This preserves exact93 model/thinking/sampler/'
    'max_tokens2048 and sends one native HTTP request with120s, no wrapper timeout/retry. '
    'Record final, reasoning length, finish_reason and latency. A slow or length-finished response is '
    'not a useful early progress signal, regardless of semantic content. No source/runtime promotion.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-thinking94.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')

source = (root / 'scratchpad/c03-progress-activity87.py').read_text(encoding='utf-8')
source = source.replace("'astra-progress-activity87'", "'astra-progress-sampling95'")
source = source.replace("for variant in ('request_interpretation',):", "for variant in (0, 1, 2):")
source = source.replace("if variant == 'request_interpretation':", "if isinstance(variant, int):")
source = source.replace('            client.begin_request(40)', '''            payload.update(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
                presence_penalty=1.5, repeat_penalty=1.0, seed=variant)
            client.begin_request(40)''')
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Non-thinking role-sampler comparison against exact87 six data-activity packets and original '
    'progress instruction. Same GGUF/backend/flags/max_tokens, no source change. Use official Qwen3.5 general '
    'non-thinking profile temperature0.7/top_p0.8/top_k20/min_p0/presence1.5/repeat1 with seeds0,1,2 fixed '
    'before execution; all18 drafts count, never select only a favourable sample. Baseline87 greedy already '
    'recorded. Judge truthful current interpretation, natural language and no execution/actor inversion. '
    'No functions/publication/UI/audio/reserve or runtime promotion.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-sampling95.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
