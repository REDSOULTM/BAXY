"""Private local HTTP observation; delegates unchanged to production transport."""
import itertools
import json
import os
from pathlib import Path
import threading
import time
from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product360-private'
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



