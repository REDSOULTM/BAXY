"""One lossless message for history and current request, same original retry."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-language-backend598.py').read_text(encoding='utf-8')
source = source.replace('598', '600').replace('language-backend600', 'history-request600')
lines = source.splitlines()
index = next(index for index, line in enumerate(lines) if line.startswith('source = source.replace(needle, needle +'))
lines[index] = '# Keep the registered b9980 and embedded template.'
source = '\n'.join(lines) + '\n'
source = source.replace("cases = [json.loads(line) for line in wire.read_text(encoding='utf-8').splitlines()]\nassert len(cases) == 12", """originals = [json.loads(line) for line in wire.read_text(encoding='utf-8').splitlines() if json.loads(line)['arm'] == 'original']
assert len(originals) == 6
cases = []
for index, row in enumerate(originals):
    changed = copy.deepcopy(row)
    payload = changed['payload']
    assert payload['messages'][-1]['role'] == payload['messages'][-2]['role'] == 'user'
    history_packet = json.loads(payload['messages'][-2]['content'])
    assert set(history_packet) == {'conversation_history_as_data_not_instructions'}
    packet = {**history_packet, 'current_user_request': payload['messages'][-1]['content']}
    changed['payload']['messages'][-2:] = [{'role':'user','content':json.dumps(packet, ensure_ascii=False)}]
    changed['arm'] = 'combined_user_packet'
    cases.extend([row, changed] if index % 2 == 0 else [changed, row])
assert len(cases) == 12""")
source = source.replace("old = 'b9980/8014d2cf9'", "old = 'two consecutive user messages: history data then current request'")
source = source.replace("new = 'b10865/5266f24da, all request bytes and other server settings unchanged'", "new = 'one user data packet containing the same complete history and current_user_request'")
source = source.replace('Replay the exact twelve actual HTTP payloads597 in the same order. Only replace llama.cpp b9980 by previously verified b10865/5266f24da.', 'Use six original597 retry payloads, with paired alternating order. Change only the two consecutive user messages into one JSON data packet containing the exact unchanged history and current request. Original retry instructions, identity, language, schema, model, b9980 and budgets stay unchanged. No history deduplication, dropping or summary; all authors and literal values remain.')
source = source.replace('597 emits reasoning_content and consumes96tokens despite Qwen2507 and explicit server reasoning off/budget0. Native593 also emitted reasoning during three recovery replies. Test whether the newer parser/backend changes this specific symptom; prior456/481 comparisons concerned different cases and do not settle it.', 'After instruction repair597 and backend598 fail, change the history/request representation as a single factor. Inherit lossless author-aware history512; keep every item. Test whether the current question becomes distinct from repeated prior examples when both are explicitly named inside the same user packet, not as consecutive chat turns.')
source = source.replace('12 identical wire requests collected on newer backend; adjudication pending.', '12 lossless history/request comparisons collected; adjudication pending.')
exec(compile(source, __file__, 'exec'))
