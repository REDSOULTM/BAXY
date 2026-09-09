from pathlib import Path

p=Path(__file__).with_name('c03-native-scope-probe.py')
s=p.read_text(encoding='utf-8').replace("out=base/'astra-native-scope'", "out=base/'astra-native-scope-guarded'")
s=s.replace("        payload={**payload,'tool_choice':'auto'}", "        if 'tools' in payload: payload={**payload,'tool_choice':'auto'}")
s=s.replace('client=Client();gpu=', 'client=Client();client._native_tool_policy_enabled=True;gpu=')
s=s.replace("client._post_native_tool_selection(case['text'],names,contracts,[])", "client.decide_turn(case['text'],list(found.values()),history=[])")
s=s.replace('existing native selector with tool_choice AUTO inherited from tranche35.', 'Full existing LlmRuntime.decide_turn using inherited native AUTO instead of primary JSON; preserve parallel semantic/count/language/compatibility validation. Compare with the raw native selector from astra-native-scope.')
exec(compile(s,str(Path(__file__)),'exec'))
