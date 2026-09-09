from pathlib import Path

source = Path(__file__).with_name('c03-knowledge-one-sentence.py').read_text(encoding='utf-8')
source = source.replace('astra-knowledge-one-sentence', 'astra-knowledge-budget')
source = source.replace("'stages':['brief_by_request']", "'stages':['current_256','brief_by_request']")
source = source.replace("        response=super()._post(payload,*args,**kwargs)", "        payload = {**payload, 'max_tokens': 256}\n        response=super()._post(payload,*args,**kwargs)")
source = source.replace('Five BAXY chat calls:', 'Ten BAXY chat calls with max_tokens256, compared with retained identical stages at128:')
source = source.replace('context, budgets, sampling and validation remain identical.', 'context, sampling and validation remain identical. This probe increases only the output budget from128 to256 for each retained policy.')
exec(compile(source, str(Path(__file__)), 'exec'))
