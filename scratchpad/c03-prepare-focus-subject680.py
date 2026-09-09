"""Seal the failed seven-case product panel and declare the relative-clause repair."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
helper = (root / 'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base / 'astra-survey-focus679'
private = home / 'C03-survey-focus679-private'
assert not (out / 'RESULT.json').exists()
panel = read(private / 'panel.json')
finals = [r for r in rows(private / 'capture/events.jsonl') if r.get('type') == 'terminal']
assert len(panel) == len(finals) == 7
compose = rows(private / 'compose-audit.jsonl')
failed = {'focus-mixed', 'focus-title-es'}
adjudication = []
for case, final in zip(panel, finals):
    is_failed = case['case_id'] in failed
    assert final['kind'] == ('composition_failed' if is_failed else 'published_final')
    adjudication.append({**case, 'terminal': final, 'verdict': 'failed' if is_failed else 'correct'})
write(private / 'adjudication.json', adjudication)
report = ['# Producto679: cinco respuestas correctas de siete']
for row in adjudication:
    report += ['## ' + row['case_id'], row['text'], row['terminal']['final'], row['verdict']]
report += ['## Borradores rechazados y payloads', *[
    json.dumps(r, ensure_ascii=False) for r in compose if r.get('trace') in {'t4', 't6'}
]]
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
note = '''# 679 — foco correcto en Windows; producto 5/7

Original H0104 y cuatro variantes publican respuestas veraces. La variante mezclada y la petición de nombre terminan en composition_failed; no se adjudica el diagnóstico terminal como prosa visible. Ambas tienen window.active verificado y ChatGPT maximizada coincide en snapshots independientes antes/después.

En la petición de nombre, el primer borrador «ChatGPT» es suficiente, pero el verificador interpreta la relativa «que está en primer plano» como otra pregunta de foco y lo rechaza. Rechaza también «La ventana en primer plano se llama "ChatGPT"». Es una falsa omisión introducida por cobertura676. En mezcla, el borrador «Ahora tiene focus el ventanal de ChatGPT» ya tiene un término impropio y el verificador tampoco reconoce su orden invertido. No se adjudica ese borrador como calidad válida ni se resuelve cambiando la entrada del usuario.

GPU3497,559MiB/RAM2368,020MiB/50,969s sin infracciones; sin UI/voz conjunta. H0104 sigue abierto, encuesta26cubiertos/716abiertos/0NA. No nueva promoción de modelo. Fuente680 abordará sólo la pérdida de alcance de la relativa, con controles de preguntas explícitas y contradicciones; el borrador mixto requiere diagnóstico independiente.
'''
seal(out, private, {'correct': 5, 'total': 7, 'failed_cases': sorted(failed),
    'resources': read(out / 'resources.json'), 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
    'goal_complete': False, 'ui_or_voice_credit': False}, note,
    ['panel.json', 'capture/events.jsonl', 'compose-audit.jsonl', 'turn-audit.jsonl',
     'foreground-before.json', 'foreground-after.json', 'adjudication.json', 'RESULT.md'])

out = base / 'astra-focus-subject-source680'
out.mkdir(exist_ok=False)
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind']
         for p in (root / folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode() + b'\n' + sha(files[name]).encode() + b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    path = root / 'experiments/stt_quality' / name
    data = path.read_bytes()
    old = b'fe4e7d0aaac35a6b7a47e92702ee1ab43b2b0d13b6b173bf70f395333c6e4099'
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, tree.encode()))
owners = read(base / 'astra-focus-coverage-source676/PREREG.json')['owner_tests']
owners = sorted(set(owners + ['tests/test_c03_window_focus_subject_order.py']))
for suffix, name in [('baseline', 'BASELINE'), ('focal', 'FOCAL')]:
    (out / (name + '.log')).write_bytes((Path(os.environ['TEMP']) / f'c03-focus-subject680-{suffix}.log').read_bytes())
assert '9 failed, 14 passed' in (out / 'BASELINE.log').read_text(encoding='utf-8-sig')
assert '344 passed' in (out / 'FOCAL.log').read_text(encoding='utf-8-sig')
write(out / 'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': False,
    'parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'sources': {name: sha(root / name) for name in ['src/baxy_mind/window_prose_facts.py',
        'src/baxy_mind/llm.py', 'tests/test_c03_window_focus_subject_order.py']},
    'python_tree_sha256': tree, 'python_files': len(files), 'owner_tests': owners,
    'design': 'Remove only a window-identifying relative clause when deciding whether focus was asked. Preserve the main predicate and all contradiction checks. No native request or model change.',
    'baseline': {'failed': 9, 'passed': 14}, 'focal_passed': 344,
    'next': 'Owners, declarations, Fast, then exact seven-query product681. Mixed wording remains independent and must not receive coverage by this patch.'})
print({'product679': '5/7', 'source680_adopted': False, 'owners': len(owners), 'tree': tree})
