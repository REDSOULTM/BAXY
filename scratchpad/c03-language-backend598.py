"""Same effective597 requests, only a previously verified newer backend changes."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-guard-boundary594.py').read_text(encoding='utf-8')
source = source.replace('594', '598').replace('guard-boundary598', 'language-backend598')
start = source.index('capture = [')
end = source.index('\nmanifest = ', start)
source = source[:start] + '''wire = private.parent / 'C03-language-wire597-private/requests.jsonl'
cases = [json.loads(line) for line in wire.read_text(encoding='utf-8').splitlines()]
assert len(cases) == 12
old = 'b9980/8014d2cf9'
new = 'b10865/5266f24da, all request bytes and other server settings unchanged'
write(private / 'panel.json', cases)
''' + source[end:]
needle = "command[command.index('--log-file') + 1] = str(private / 'server.log')"
source = source.replace(needle, needle + "\ncommand[0] = 'D:/BAXYRuntime/assets/llama-b10865-cuda12.4/llama-server.exe'\nassert sha(command[0]) == '16eac28198d6218a9892f08dac0f0c81612a72872b4dd9741c4c6c36f88c4fd7'")
source = source.replace('Exact native grammar/sampling/template593, paired original vs replacing only incomplete-effect definition.16 preregistered cases, first owner literal and15 development contrasts. Alternate arm order. No classifier bypass, output rewriting, effects, model or registration change.', 'Replay the exact twelve actual HTTP payloads597 in the same order. Only replace llama.cpp b9980 by previously verified b10865/5266f24da. Same model, sampler, full prompt, JSON schema,96token budget, three slots,4096context per slot, no-mmap/q8KV. Preserve both original and candidate597 arms. No registration change or product effects.')
source = source.replace('Ambiguous wording classifies conversational noise as an incomplete effect. Require an actual request for external reading/change before missing arguments can imply incomplete_effect.', '597 emits reasoning_content and consumes96tokens despite Qwen2507 and explicit server reasoning off/budget0. Native593 also emitted reasoning during three recovery replies. Test whether the newer parser/backend changes this specific symptom; prior456/481 comparisons concerned different cases and do not settle it.')
source = source.replace('Every response must finish normally and match its preregistered request_type. Stable conversation must count zero; two requested effects must count multiple. No adoption from fixing H0012 while losing real effects. Final product and more generalization remain mandatory.', 'Compare every final, reasoning channel, stop cause, effective template, usage and resources with597. Identity BAXY in English; human names Sofia/Isabel; Spanish identity and English RAM controls. No adoption from an empty reasoning channel if public output remains wrong. Any result is a native backend comparison, not joint product acceptance.')
start = source.index('    for index, (case_id, text, expected) in enumerate(cases):')
end = source.index('    complete = True', start)
source = source[:start] + '''    with urllib.request.urlopen(url + '/props', timeout=10) as response:
        write(private / 'props.json', json.load(response))
    for row in cases:
        payload = row['payload']
        append(private / 'requests.jsonl', row)
        begin = time.monotonic()
        request = urllib.request.Request(url + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        append(private / 'responses.jsonl', {**row, 'seconds':time.monotonic()-begin, 'response':result})
        assert not violations
        print('Collected ' + row['case_id'] + ' ' + row['arm'], flush=True)
''' + source[end:]
source = source.replace('32 native classifications collected; adjudication pending.', '12 identical wire requests collected on newer backend; adjudication pending.')
exec(compile(source, __file__, 'exec'))
