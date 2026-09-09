"""Private local HTTP observation; delegates unchanged to production transport."""
import itertools
import json
import os
from pathlib import Path
import threading
import time
from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-observe-identity593-private'
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




original_command = LlmRuntime._server_command
def observed_command(self):
    command = [*original_command(self), '--verbosity', '4', '--log-file', str(private/'server.log')]
    (private/'effective-server-command.json').write_text(json.dumps(command, indent=2)+'\n', encoding='utf-8')
    return command
LlmRuntime._server_command = observed_command


original_shape = LlmRuntime._verify_semantic_effect_shape
original_chat = LlmRuntime.chat
def record_boundary(value):
    with lock, (private/'boundaries.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': time.monotonic(), **value}, ensure_ascii=False) + '\n')
def observed_shape(self, text):
    result = original_shape(self, text)
    record_boundary({'kind': 'effect_shape', 'text': text, 'result': result})
    return result
def observed_chat(self, text, *args, **kwargs):
    record_boundary({'kind': 'chat_input', 'text': text, 'args': args, 'kwargs': kwargs})
    return original_chat(self, text, *args, **kwargs)
LlmRuntime._verify_semantic_effect_shape = observed_shape
LlmRuntime.chat = observed_chat
