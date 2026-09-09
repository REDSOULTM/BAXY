"""Repeat only592's first11 turns, observing native classification and chat inputs."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source = source.replace('592', '593')
source = source.replace('conversation-regression593', 'observe-identity593')
source = source.replace('C03-conversation-profile593', 'C03-observe-identity-profile593')
needle = "(private / 'panel.json').write_text"
assert source.count(needle) == 1
source = source.replace(needle, "panel = [row for row in panel if row['group'] == 'identity']\n" + needle)
old = "source = source.replace(old, \"str(root/'src')\")"
assert source.count(old) == 1
observer = '''hook = root / 'scratchpad/c03-owner593-hook'
hook.mkdir(exist_ok=False)
observer = (root / 'scratchpad/c03-owner521-hook/sitecustomize.py').read_text(encoding='utf-8')
observer = observer.replace('C03-private-product521-private', 'C03-observe-identity593-private')
observer += '\\n' + """
original_shape = LlmRuntime._verify_semantic_effect_shape
original_chat = LlmRuntime.chat
def record_boundary(value):
    with lock, (private/'boundaries.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': time.monotonic(), **value}, ensure_ascii=False) + '\\\\n')
def observed_shape(self, text):
    result = original_shape(self, text)
    record_boundary({'kind': 'effect_shape', 'text': text, 'result': result})
    return result
def observed_chat(self, text, *args, **kwargs):
    record_boundary({'kind': 'chat_input', 'text': text, 'args': args, 'kwargs': kwargs})
    return original_chat(self, text, *args, **kwargs)
LlmRuntime._verify_semantic_effect_shape = observed_shape
LlmRuntime.chat = observed_chat
"""
(hook/'sitecustomize.py').write_text(observer, encoding='utf-8', newline='\\n')
source = source.replace(old, "str(root/'scratchpad/c03-owner593-hook')+os.pathsep+str(root/'src')")'''
source = source.replace(old, observer)
source = source.replace(
    'Shared source590 product, base registered runtime, built-in diagnostics only. Twenty-one owner survey literals plus fourteen ES/EN/mixed development variants across identity, greeting, gratitude and small talk. Same dialogue session, exact panel order. No parameter, payload, classification, draft or output replacement. No adapter override. This is development regression, not blind acceptance.',
    'Repeat only the first11 identity turns from592 in the same order and isolated empty profile. Source590 and base registered runtime, same sampling. Observe native POST input/response plus actual effect-shape return and chat arguments by delegating unchanged to their source methods. No classification, draft, payload or output replacement; no adapter. Observer I/O can affect timing: this is causal diagnosis, not a clean latency benchmark or blind acceptance.'
)
source = source.replace(
    'Read every final and progress against the individual panel criterion; correct language, natural response and no invented facts or effects. Every literal receives an individual verdict; common family does not grant coverage by itself. Generalization variants support only their declared group. No UI or voice credit from this hidden conductor.',
    'Determine the exact first transformation for H0012 (raw knowledge to unsupported) separately from the English history/language failures. Capture actual request-type classification, chat kind/history/language and all failed retry payloads before proposing a repair. Do not infer one shared cause, add literal aliases or claim that an omitted history_users audit field means no history was sent. Preserve all11 finals and regressions. No UI/voice credit.'
)
exec(compile(source, __file__, 'exec'))
