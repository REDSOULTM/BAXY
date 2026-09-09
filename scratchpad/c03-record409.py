from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-descriptor-mind409'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-descriptor-mind409-private'
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8')]
cases = {c['id']: c for c in json.loads((root / 'scratchpad/c03-descriptor-mind409-cases.json').read_text(encoding='utf-8'))['cases']}
report = ['# 409 — decisiones con E5 cargado:11/13→13/13', '',
    'Dos sidecars secuenciales, trece sintéticos por brazo. Mismo scope405, historia, modelo y sampler; sólo descripción system.identity exacta387 cambia. La selección mejora usernameEN/ES; cuatro consultas de cuenta eligen identity, tres recursos status, concepto/prohibición y cuatro nombres personales permanecen útiles sin operación. No regresiones útiles en estos controles.', '',
    'Ambos alcanzaron recursos semánticos:24,609s y26,234s desde el observador. El español de Álvaro contiene el carácterÁ real(U+00C1), no una secuencia de escape visible. No son efectos ejecutados ni productoUI/voz/frescos. Manifiesto intacto, procesos cerrados. La consulta usernameEN fría sigue pendiente: en408 el descriptor la deja en rango20, fuera del top4 para retirar conocimiento cerrado.', '',
    'Se adopta la descripción y la abstención del scope de recursos ante cuenta/usuario. Se excluyen de la versión de producto las palabras genéricas identidad/identity usadas en el hook405: la identidad de GPU pertenece a system.status. Los nuevos controles410 preservan ese alcance; no hay mapeo fijo hacia system.identity.', '']
for row in rows:
    reply = row['reply']
    useful = not (row['variant'] == 'baseline' and row['id'] in {'username-en', 'username-es'})
    report += [f"## {row['variant']} / {row['id']} — {'útil' if useful else 'fallo'}", '',
               cases[row['id']]['request'], '',
               f"{reply['kind']}; operación {reply.get('operation')}; {row['seconds']}s.", '',
               '> ' + (reply.get('reply') or reply.get('question') or '(propuesta estructurada)').replace('\n', '\n> '), '']
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [out / n for n in ['PREREG.json', 'replies.jsonl', 'RESULT.md', 'EXIT.json', 'wait-baseline.json', 'wait-descriptor.json']]
paths += [private / n for n in ['catalog-baseline.json', 'catalog-descriptor.json', 'http-posts.jsonl', 'turn-audit.jsonl', 'startup-baseline.jsonl', 'startup-descriptor.jsonl', 'hook/sitecustomize.py']]
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')
source_out = base / 'astra-account-catalog410'
source_out.mkdir(exist_ok=False)
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'method': 'Adopt exact descriptor387 proven useful in409 (11/13→13/13 full warm mind), and scope405 limited to account/user words so GPU identity remains resource status. No forced operation/new classifier/model/prompt. Twelve focal tests: six account/compound reads must abstain; six OS/CPU/GPU reads retain status. Baseline5failed7passed0skips1.41s. Then owners/Fast and actual source diagnostic. Cold usernameEN remains open.',
    'prior_source': {p: sha(root / p) for p in ['src/baxy_mind/effect_intent.py', 'src/Baxy.Kernel/Operations/ProductCatalog.cs']},
    'validation': 'Focal, Python owners effect/state/planner and Kernel owner; Fast. No Full during repair, no UI/voice claim.'}
(source_out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(source_out / 'baseline.log').write_bytes((Path(os.environ['TEMP']) / 'c03-account-catalog410-baseline.log').read_bytes())
print(json.dumps({'409_rows': len(rows), '410_preregistered': True}))
