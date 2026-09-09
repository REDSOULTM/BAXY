"""Explicit diagnostic voice events for App UI194; never installed in product."""
from pathlib import Path
import json
import os
import threading
import time

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui194-private'
private.mkdir(parents=True,exist_ok=True)
from baxy_mind.voice import VoiceEngine
from baxy_mind.llm import LlmRuntime

original_init=VoiceEngine.__init__
original_compose=LlmRuntime.compose_user_message
active_engine=None
pending_new_request=None
lock=threading.Lock()

def log(row):
    with lock, (private/'events.jsonl').open('a',encoding='utf-8') as handle:
        handle.write(json.dumps({'time':time.monotonic(),**row},ensure_ascii=False)+'\n')

def observe_compose(self,user_text,intent,facts,**kwargs):
    global pending_new_request
    with lock:
        new_request=pending_new_request if facts.get('voiceFeedback') else None
        if new_request:pending_new_request=None
    if new_request:
        log({'event':'new_request_during_feedback_composition','text':new_request})
        # New request reaches the App while the old composer is running. The
        # bounded delay only controls this diagnostic race, not product timeouts.
        active_engine._on_transcript(new_request)
        time.sleep(.5)
    return original_compose(self,user_text,intent,facts,**kwargs)

LlmRuntime.compose_user_message=observe_compose

def controls(engine):
    global pending_new_request
    seen=set();deadline=time.monotonic()+540
    while time.monotonic()<deadline:
        path=private/'command.json'
        if path.is_file():
            try:command=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError):command=None
            if command and command['id'] not in seen:
                seen.add(command['id'])
                status=engine.status()
                if not status.get('listening'):
                    log({'event':'command_rejected','id':command['id'],'reason':'not_listening'})
                elif command['kind'] in {'wake','uncertain','supersede'}:
                    log({'event':'diagnostic_command','command':command})
                    if command['kind']=='uncertain':
                        engine._emit('ignored',reason='transcript_doubtful')
                    else:
                        if command['kind']=='supersede':
                            with lock:pending_new_request='¿Qué hora es?'
                        engine._emit('wake',backend='diagnostic194',armedSeconds=8)
                else:log({'event':'command_rejected','id':command['id'],'reason':'unknown_kind'})
        time.sleep(.05)

def observed_init(self,*args,**kwargs):
    global active_engine
    original_init(self,*args,**kwargs)
    active_engine=self
    log({'event':'voice_engine_created','pid':os.getpid()})
    threading.Thread(target=controls,args=(self,),daemon=True,name='diagnostic-ui194').start()

VoiceEngine.__init__=observed_init
log({'event':'hook_loaded','pid':os.getpid()})
