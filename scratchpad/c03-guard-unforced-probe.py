from pathlib import Path

p=Path(__file__).with_name('c03-guard-format-probe.py')
s=p.read_text(encoding='utf-8').replace("out=base/'astra-guard-format'", "out=base/'astra-guard-unforced'")
s=s.replace("        payload['response_format']={'type':'json_schema','json_schema':{'name':'baxy_semantic_effect_guard','strict':True,'schema':schema}}", "        payload.pop('response_format', None)")
s=s.replace('Replace only compact GBNF with original equivalent JSON Schema.', 'Remove only grammar/response_format; model may emit any serialization with the identical classification prompt and64tokenbudget. Diagnostic only; no unparsed output grants authority.')
exec(compile(s,str(Path(__file__)),'exec'))
