"""Private local HTTP observation; delegates unchanged to production transport."""
import itertools
import json
import os
from pathlib import Path
import threading
import time
from baxy_mind.llm import LlmRuntime

private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product515-base-private'
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

_writer_view_post = LlmRuntime._post
def _observed_writer_view(self, payload, *args, **kwargs):
    import copy
    before = copy.deepcopy(payload)
    changes = []
    if 'base' == 'view':
        messages = payload.get('messages', [])
        allowed = {'memory.enable','memory.disable','memory.save','memory.sensitive.save','memory.correct'}
        for index, message in enumerate(messages):
            if message.get('role') != 'user' or not isinstance(message.get('content'), str):
                continue
            lines = message['content'].splitlines()
            for line_index, line in enumerate(lines):
                if not line.startswith('situation: '):
                    continue
                view = json.loads(line.removeprefix('situation: '))
                if (view.get('kind') != 'status' or view.get('outcome') != 'completed'
                        or view.get('operation') not in allowed or not isinstance(view.get('seen'),dict)):
                    continue
                prior_view = copy.deepcopy(view)
                view.pop('state',None)
                for key in ['corrected','sensitive','replayed']:
                    if view['seen'].get(key) is False:
                        view['seen'].pop(key)
                if view == prior_view:
                    continue
                lines[line_index] = 'situation: ' + json.dumps(view,ensure_ascii=False)
                payload = copy.deepcopy(payload)
                payload['messages'][index]['content'] = '\n'.join(lines)
                changes.append({'original_view':prior_view,'effective_view':view})
    with (private/'writer-view.jsonl').open('a',encoding='utf-8') as output:
        output.write(json.dumps({'mode':'base','changes':changes,'before':before,'after':payload},ensure_ascii=False)+'\n')
    return _writer_view_post(self,payload,*args,**kwargs)
LlmRuntime._post = _observed_writer_view
