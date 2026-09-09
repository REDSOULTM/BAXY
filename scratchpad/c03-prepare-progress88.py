from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-activity87.py').read_text(encoding='utf-8')
source = source.replace('from baxy_mind.llm import LlmRuntime',
    'from baxy_mind.llm import LlmRuntime, _PROGRESS_MESSAGE_INSTRUCTION')
source = source.replace("'astra-progress-activity87'", "'astra-progress-instruction88'")
source = source.replace("for variant in ('request_interpretation',):", "for variant in ('activity_instruction',):")
source = source.replace("if variant == 'request_interpretation':", "if variant == 'activity_instruction':")
needle = '            client.begin_request(40)'
replacement = '''            changed = 0
            for message in payload['messages']:
                if _PROGRESS_MESSAGE_INSTRUCTION in message.get('content', ''):
                    message['content'] = message['content'].replace(_PROGRESS_MESSAGE_INSTRUCTION,
                        "Write a brief first-person progress update about the current activity stated in situation. "
                        "The person's request describes their goal, not what has already started. "
                        "During request interpretation, describe your work on understanding the request, "
                        "not execution of the requested action. Do not answer the request or report unobserved results.")
                    changed += 1
            assert changed == 1
            client.begin_request(40)'''
assert needle in source
source = source.replace(needle, replacement)
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Native prototype after85/87 data-only limitations: exact87 state and same six82 packets; '
    'replace only the existing progress instruction to narrate actual activity instead of treating the requested '
    'goal as proof of execution. No appended prompt/validator/retry, source/model/sampler change. Compare with87 '
    'already recorded; do not rerun baseline. Known-understanding fixture phase assumed. '
    'No effects, publication/UI/audio/reserve or promotion.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-instruction88.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
