from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
failed = base / 'astra-retrieval406'
(failed / 'RESULT.md').write_text('# 406 — fallo del arnés, no aceptación\n\nEl arnés no propagó PYTHONPATH al worker iniciado con -m baxy_mind.router_worker; éste cerró antes de ready. Nueve filas lexical, ninguna semantic. La única corrección de406b propaga src al proceso hijo y sí permite medir E5. No atribuir este fallo al arranque del producto.\n', encoding='utf-8')
(failed / 'EXIT.json').write_text(json.dumps({'completed': False, 'exit_code': 1, 'failure': 'encoder worker closed; harness omitted child PYTHONPATH'}) + '\n', encoding='utf-8')
retrieval = base / 'astra-retrieval406b'
(retrieval / 'RESULT.md').write_text('''# 406b — recuperación semántica real, insuficiente para todas las cuentas

E5 CPU local verificado carga20,234s; catálogo/skills3,547s. Mismo catálogo405 y
nueve sintéticos. Cuatro cuentas: lexical ofrece2/4 (ES ausentes;EN rangos2/28),
E5 ofrece2/4 (ambas account rango1; ambos username ausentes). Los tres controles
de OS/RAM/CPU conservan system.status visible. No son decisiones ejecutadas.

La auditoría405 confirma retrieval=lexical, no se infiere sólo por faltantes.
Los prefijos query/passage y normalización existentes coinciden con la ficha
oficial E5 (README:18331,18424–18432). No cambio de modelo ni GPU medida.
406b corrige sólo el PYTHONPATH faltante del arnés406, cuya evidencia se conserva.
''', encoding='utf-8')
out = base / 'astra-retrieval-startup407'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private'
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8')]
cases = json.loads((root / 'scratchpad/c03-account-scope405-cases.json').read_text(encoding='utf-8'))['cases']
report = ['# 407 — promoción funciona; ventana lexical inicial y dos fallos posteriores', '',
    'Arranque completo real: snapshot lexical1,250s; E5 ready20,766s; corpus cache25156 listo20,984s; recursos semánticos24,438s. No se demostró bloqueo permanente ni agotamiento185s. No cambiar timeout ni ordenar de nuevo el arranque con esa hipótesis refutada.', '',
    'Misma abstención de alcance405, esperando la promoción:7/9 útiles (405 frío6/9). Ambas accountES/EN seleccionan system.identity; usernameEN sigue explicit_conversation con falsa negación de acceso, usernameES selecciona system.status. OS/RAM/CPU/concepto/prohibición conservados. Todos los audits ahora semantic.', '',
    'Sin efectos ni edición de fuente/promoción de runtime. Sin UI/audio físico ni nuevo perfil de recursos. Manifiesto intacto; procesos cerrados. Evidencia completa de drafts privada. La espera sólo es un método diagnóstico; no se añade al producto.', '']
for case, row in zip(cases, rows, strict=True):
    reply = row['reply']
    report += [f"## {case['id']}", '', case['request'], '',
               f"{reply['kind']}; operación {reply.get('operation')}; {row['seconds']}s.", '',
               '> ' + (reply.get('reply') or reply.get('question') or '(propuesta estructurada)').replace('\n', '\n> '), '']
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
for folder, names in [(failed, ['PREREG.json', 'ranks.jsonl', 'RESULT.md', 'EXIT.json']),
                      (retrieval, ['PREREG.json', 'ranks.jsonl', 'READINESS.json', 'RESULT.md', 'EXIT.json']),
                      (out, ['PREREG.json', 'replies.jsonl', 'wait.json', 'evidence-initial.json', 'evidence-after.json', 'RESULT.md', 'EXIT.json'])]:
    paths = [folder / n for n in names]
    if folder == out:
        paths += [private / n for n in ['http-posts.jsonl', 'turn-audit.jsonl', 'startup-observer.jsonl', 'hook/sitecustomize.py']]
    (folder / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')

source = (root / 'scratchpad/c03-retrieval406b.py').read_text(encoding='utf-8-sig').replace('astra-retrieval406b', 'astra-retrieval-descriptor408')
source = source.replace('import hashlib\n', 'import hashlib\nimport copy\n')
source = source.replace("prereg = {'utc':", "replacement = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity-scope387/PREREG.json').read_text(encoding='utf-8'))['new_description']\nprereg = {'new_description': replacement, 'utc':")
source = source.replace("'method': 'Same authenticated", "'new_evidence': 'Reuse exact descriptor387, previously rejected for selection with all tools visible. Here406b/407 prove missing retrieval for account synonyms, a different first failing boundary. Change only catalog description and compare lexical/semantic visibility; no further prompt variant or policy claim.',\n    'method': 'Same authenticated")
source = source.replace("    measure('semantic', semantic)\n", """    measure('semantic', semantic)
    variant_catalog = copy.deepcopy(catalog)
    next(c for c in variant_catalog['capabilities'] if c['name'] == 'system.identity')['description'] = replacement
    variant_tools = configure_tools(variant_catalog['capabilities'])
    variant_lexical, _ = _create_planner_resources(variant_tools)
    measure('descriptor-lexical', variant_lexical)
    variant_semantic, _ = _create_planner_resources(variant_tools, encoder)
    measure('descriptor-semantic', variant_semantic)
""")
target = root / 'scratchpad/c03-retrieval-descriptor408.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
print('406/406b/407 recorded;408 prepared, no source changed')
