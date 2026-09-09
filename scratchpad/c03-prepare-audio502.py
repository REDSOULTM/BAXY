"""Prepare a real protocol repeat with argument/plan boundaries, without effects."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
script = (root / 'scratchpad/c03-audio-mind499.py').read_text(encoding='utf-8-sig')
script = script.replace('499', '502')
script = script.replace('source498 positive adversative and quote repair',
                        'source501 contextual level/argument repair plus500 shared setting head')
script = script.replace('catalog.configure then turn.decide only:',
                        'catalog.configure, turn.decide and actual arguments/plan requests matching the shell:')
script = script.replace('no provider invocations, volume/mute changes, UI or speech.',
                        'no provider invocations, volume/mute changes, UI or speech. Transmit only actual selected operations to later protocol stages, never the expected list from the test case. Follow the current C# shape: plan gets the real history and expectedOperations from turn.result; direct arguments get selected operation and current text. Additional development controls cover the prior missing-level request, a contextual negative clause, a new time request and English numeric continuation.')
anchor = 'cases=[\n'
replacement = '''cases=[
 {'id':'owner49','request':by_index[49]['body'],'history':[],'expected':[],'expected_kind':'clarify'},
 {'id':'context-negative','request':'Al 37 pero no quites el silencio','history':history([49,50]),'expected':['audio.volume'],'arguments':{'level':37}},
 {'id':'new-time','request':'Dime la hora','history':history([49,50]),'expected':['system.time']},
 {'id':'context-en','request':'To 42 but tell me the time','history':[{'role':'user','content':'Set the volume of the computer'},{'role':'assistant','content':'What level would you like?'}],'expected':['audio.volume','system.time'],'arguments':{'level':42}},
'''
assert script.count(anchor) == 1
script = script.replace(anchor, replacement, 1)
anchor = '  if violations:break\n complete=not violations'
replacement = '''  binding_request = None
  if reply.get('kind') == 'plan':
   binding_request = {'id':case['id']+'-plan','type':'plan','text':case['request'],'history':case['history'],'expectedOperations':reply['effectOperations']}
  elif reply.get('kind') == 'action' and reply.get('operation'):
   selected = next(c for c in capabilities if c['name'] == reply['operation'])
   if selected['argumentsSchema'].get('properties'):
    binding_request = {'id':case['id']+'-arguments','type':'arguments','operation':reply['operation'],'text':case['request']}
  if binding_request is not None:
   append(private/'binding-requests.jsonl',binding_request)
   bind_start = time.monotonic()
   try: binding_reply = client.request(binding_request,90)
   except Exception as error: binding_reply = {'error':type(error).__name__+': '+str(error)}
   binding_row = {'id':case['id'],'type':binding_request['type'],'seconds':round(time.monotonic()-bind_start,3),'reply':binding_reply}
   append(out/'bindings.jsonl',binding_row)
   print(json.dumps({'binding':case['id'],'type':binding_request['type'],'reply':binding_reply},ensure_ascii=True),flush=True)
  if violations:break
 complete=not violations'''
assert script.count(anchor) == 1
script = script.replace(anchor, replacement, 1)
target = root / 'scratchpad/c03-audio-mind502.py'
assert not target.exists()
target.write_text(script, encoding='utf-8')
print('502 prepared:14 current/development turns, actual bindings, no effects.')
