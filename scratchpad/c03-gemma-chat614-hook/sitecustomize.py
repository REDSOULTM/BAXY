"""Diagnostic Gemma chat profile and wire observation; no semantic rewriting."""
from contextvars import ContextVar
from pathlib import Path
import copy
import itertools
import json
import os
import threading
from baxy_mind.llm import LlmRuntime

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-gemma-product614-private'
private.mkdir(parents=True,exist_ok=True)
in_chat=ContextVar('c03_gemma_chat614',default=False)
lock=threading.Lock()
sequence=itertools.count()
original_chat=LlmRuntime.chat
original_post=LlmRuntime._post
original_command=LlmRuntime._server_command

def append(value):
    with lock,(private/'http-posts.jsonl').open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False)+'\n')

def chat(self,text,*args,**kwargs):
    if len(args)>=3:
        args=(*args[:2],1.0,*args[3:])
    else:
        kwargs['temperature']=1.0
    token=in_chat.set(True)
    try:
        return original_chat(self,text,*args,**kwargs)
    finally:
        in_chat.reset(token)

def post(self,payload,*args,**kwargs):
    wire=copy.deepcopy(payload)
    if in_chat.get():
        wire.update(top_p=.95,top_k=64,min_p=0.0,presence_penalty=0.0,repeat_penalty=1.0)
    prefix=[]
    for message in wire.get('messages',[]):
        if message.get('role')!='system':
            break
        prefix.append(message['content'])
    if len(prefix)>1:
        wire['messages']=[{'role':'system','content':'\n\n'.join(prefix)},*wire['messages'][len(prefix):]]
    number=next(sequence)
    append({'id':number,'stage':'request','role':'chat' if in_chat.get() else 'other','payload':wire})
    try:
        result=original_post(self,wire,*args,**kwargs)
    except Exception as error:
        append({'id':number,'stage':'failure','error_type':type(error).__name__,'detail':str(error)})
        raise
    append({'id':number,'stage':'response','response':result})
    return result

def command(self):
    result=original_command(self)
    if '--lazy-mode' in result:
        result[result.index('--lazy-mode')+1]='on'
    else:
        result += ['--lazy-mode','on']
    result += ['--log-file',str(private/'server.log')]
    (private/'effective-server-command.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

LlmRuntime.chat=chat
LlmRuntime._post=post
LlmRuntime._server_command=command
