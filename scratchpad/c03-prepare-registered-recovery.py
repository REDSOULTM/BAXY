from pathlib import Path
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
old='astra-presentation-product-qwen'
new='astra-registered-development-recovery-qwen'
out=base/new
out.mkdir(exist_ok=False)
commands=[json.loads(line) for line in (base/(old+'.turns.jsonl')).read_text(encoding='utf-8').splitlines()]
for mode, text in [('reject','¿Qué hora es?'),('timeout','What time is it?'),('exhaust','Dime la hora, please.')]:
    commands.extend([{'cmd':'inject','mode':mode},{'cmd':'turn','text':text},{'cmd':'restore'},{'cmd':'turn','text':text}])
(base/(new+'.turns.jsonl')).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in commands),encoding='utf-8')
s=(root/'scratchpad/c03-presentation-product-qwen.py').read_text(encoding='utf-8')
s=s.replace(old,new).replace('c03-presentation-product-qwen.py','c03-registered-development-recovery.py')
s=s.replace("         'artifacts/comprobaciones/C03/"+new+"/profile/sitecustomize.py',\n",'')
start=s.index("for name in ['BAXY_MIND_LLM_GGUF'")
end=s.index("app=ROOT/",start)
s=s[:start]+'''for name in list(env):
    if name.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or name in {'BAXY_ASSET_DESCRIPTOR', 'PYTHONPATH'}:
        env.pop(name,None)
env.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out/'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out/'raw-replies.jsonl'),
           BAXY_APP_TRACE=str(out/'shell-trace.jsonl'))
''' +s[end:]
start=s.index("                readiness=out/'resource-readiness.jsonl'")
end=s.index("                    commands=",start)
s=s[:start]+'''                ready_components = set()
                if time.monotonic()-started > 50:
''' +s[end:]
s=s.replace("'method':'Inherited conductor and 21 requests, Qwen3 4B Instruct base without LoRA or sampling overrides; GGUF override and q8 KV are explicit diagnostic settings. Read-only audit captures actual payloads and replies; kernel/providers/composition and app publication run normally. Own empty fixture used for exact close/confirmation; current-state facts are observed, not replayed. Different live history from synthetic ablation: do not attribute every difference to one layer. No graphical UI observation from conductor.'", "'method':'Registered Qwen runtime with no model/KV/PythonPath/sampling overrides or sitecustomize instrumentation. Existing 21 consumed development requests, then separate reject/timeout/exhaust injections each followed by restore and a normal request in the SAME process/profile/session. Recovery requests do not count as normal acceptance. Existing own empty window fixture; no user windows are closed. Conductor inherently disables wake; this run cannot prove simultaneous voice budget or graphical UI.'")
s=s.replace('Hold the documented stdin command stream open until both semantic catalog and skill registry constructors finish, or 150 seconds. Warm diagnostic, not cold-start latency or acceptance. Product source unchanged.', 'Hold stdin for 50 seconds to allow normal warmup, no readiness instrumentation or runtime overrides. Warm development and recovery, not cold-start latency or fresh acceptance.')
(root/'scratchpad/c03-registered-development-recovery.py').write_text(s,encoding='utf-8')
print('Prepared registered 21 development + separate 3 injected failures and 3 restored normal turns; not executed.')
