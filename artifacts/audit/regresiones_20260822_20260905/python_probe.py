"""Execute only selected historical pure functions, never import a runtime."""
import ast
import builtins
import json
from pathlib import Path
import re
import subprocess
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def load_pure(ref, roots):
    source = subprocess.check_output(
        ['git','show',f'{ref}:src/baxy_mind/llm.py'],cwd=ROOT).decode('utf-8-sig')
    tree = ast.parse(source)
    top = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            top[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    top[target.id] = node
    chosen = {}
    def visit(name):
        if name in chosen or name not in top:
            return
        node = top[name]
        chosen[name] = node
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                visit(child.id)
    for root in roots:
        visit(root)
    nodes = sorted({id(node):node for node in chosen.values()}.values(), key=lambda n:n.lineno)
    namespace = {'re':re,'json':json,'unicodedata':unicodedata}
    prefix = ast.parse('from __future__ import annotations').body
    exec(compile(ast.Module(body=prefix+nodes,type_ignores=[]),ref,'exec'),namespace)
    return namespace, [{'name':k,'line':v.lineno} for k,v in chosen.items()]

observation={'version':1,'utc':'2026-09-03T06:57:52.1829160+00:00','localUtcOffsetMinutes':-240}
rows=[]
for ref in ['4c9804c','26d8eab','b2505da']:
    ns,selection = load_pure(ref,['_compose_situation_payload','_message_response_language'])
    rows.append({'ref':ref,'selected_nodes':selection,
        'actual_contract':ns['_compose_situation_payload'](
            {'kind':'operation','operation':'system.time','polarity':'success',
             'verified':True,'observed':observation},'es','¿Qué hora es?')
             if '_compose_situation_payload' in ns else 'function did not exist',
        'historical_test_contract':ns['_compose_situation_payload'](
            {'kind':'operation','operation':'system.time','polarity':'success',
             'verified':True,'observed':{'localTime':'22:10'}},'es','¿Qué hora es?')
             if '_compose_situation_payload' in ns else 'function did not exist',
        'language_examples':{text:ns['_message_response_language'](text)
           for text in ['Good afternoon','define DNS in one sentence','Hola']}})
OUT.joinpath('python-probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in row.items() if k!='selected_nodes'} for row in rows],ensure_ascii=False,indent=2))
