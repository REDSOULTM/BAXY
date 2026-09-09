"""Private local HTTP observation; delegates unchanged to production transport."""
import itertools
import json
import os
from pathlib import Path
import threading
import time
from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product329-private'
private.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()
sequence = itertools.count()
original = LlmRuntime._post

def observe(self, payload, *args, **kwargs):
    number = next(sequence)
    def log(value):
        with lock, (private/'http-posts.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps({'time':time.monotonic(),'pid':os.getpid(),'id':number,**value},ensure_ascii=False)+'\n')
    log({'stage':'request','payload':payload})
    try:
        response = original(self,payload,*args,**kwargs)
    except Exception as error:
        log({'stage':'failure','errorType':type(error).__name__,'detail':str(error)})
        raise
    log({'stage':'response','response':response})
    return response

LlmRuntime._post = observe




# One-variable diagnostic, never adopted as product routing.
from baxy_mind import effect_intent
source = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-owner264-heap280/TRANSCRIPT282.json'
owner_text = json.loads(source.read_text(encoding='utf-8'))[99]['body']
owner_folded = effect_intent._strip_request_envelope(effect_intent._fold(owner_text))
original_deferred = effect_intent._has_unsupported_deferred_effect
def inspect_deferred(text):
    result = original_deferred(text)
    if text == owner_folded:
        with (private/'deferred-override.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps({'original':result,'diagnostic':False})+'\n')
        return False
    return result
effect_intent._has_unsupported_deferred_effect = inspect_deferred
