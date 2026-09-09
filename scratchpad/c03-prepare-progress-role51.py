from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-pending50.py').read_text(encoding='utf-8')
source = source.replace('astra-progress-pending50', 'astra-progress-role51')
source = source.replace('representing the request as pending data', 'making the narration task explicit')
instruction = (
    'For this turn, write a brief first-person progress update about working on the request. '
    'The requested results are not available yet. Do not answer the request, report measurements '
    'or claim completed effects. Do not ask the person to perform the work.'
)
start = source.index("    'method': ")
end = source.index('\n', start)
method = (
    'Five direct native completions from exact first payloads captured by progress-purpose50. '
    'Append one system instruction specifying the current task as first-person progress narration '
    'with no results yet. Preserve original user request and situation unchanged; same model/template/'
    'sampler/budget, no guards or retries. This restores the scoped narration responsibility '
    'present in historical44b7c45 without prescribing Sigo/Still working or an output template. '
    'Two prior data-representation variants failed; this tests task instruction instead. '
    'No source promotion, PC effects, human reserve or UI/audio acceptance.'
)
source = source[:start] + "    'method': " + repr(method) + ',' + source[end:]
start = source.index("        content = payload['messages'][-1]['content']")
end = source.index('        client.begin_request(40)', start)
source = source[:start] + "        payload['messages'][0]['content'] += '\\n' + " + repr(instruction) + '\n' + source[end:]
(root / 'scratchpad/c03-progress-role51.py').write_text(source, encoding='utf-8')
print('Prepared progress-role51 native comparison.')
