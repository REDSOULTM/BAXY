"""Adopt693 after completed Full and individually reviewed product694 evidence."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
helper = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
out = base/'astra-shared-status-source693'
assert not (out/'RESULT.json').exists()
prereg = read(out/'PREREG.json')
assert all(sha(root/name) == expected for name,expected in prereg['sources'].items())
assert read(out/'FULL_EXIT.json')['exitCode'] == 0
gate = (out/'FULL.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Full' in gate
assert 'source_quality_stage_failed:' not in gate
net = [tuple(map(int, match)) for match in re.findall(r'Con error:\s*(\d+),\s*Superado:\s*(\d+),\s*Omitido:\s*(\d+)', gate)]
assert len(net) == 5 and all(failed == 0 for failed, _, _ in net)
summaries = [line.strip() for line in gate.splitlines() if re.search(r'\d+ passed.*\bin [\d.]+s', line)]
assert summaries
summary = summaries[-1]
assert not re.search(r'\d+ (?:failed|xfailed|xpassed|errors?)', summary)
passed = int(re.search(r'(\d+) passed', summary)[1])
skipped = re.search(r'(\d+) skipped', summary)
subtests = re.search(r'(\d+) subtests passed', summary)
product = read(base/'astra-status-batch694/RESULT.json')
assert product['total'] == 73 and product['counts'].get('correct_observed_run', 0) > 35
assert product['same_inputs_order_and_criteria689'] and not product['resources']['violations']
assert '29 passed' in (out/'FOCAL.log').read_text(encoding='utf-8-sig')
note = (out/'ADOPTION_NOTE.md').read_text(encoding='utf-8')
assert note.strip() and '693' in note
result = {'adopted': True, 'sources': prereg['sources'],
    'python_tree_sha256': prereg['python_tree_sha256'], 'python_files': prereg['python_files'],
    'focal_python_passed': 29, 'full_exit': 0,
    'dotnet': {'passed': sum(r[1] for r in net), 'aggregate_skipped': sum(r[2] for r in net),
        'optional_omissions': 'Separate opt-in omissions remain in raw log; never counted as passes.'},
    'python': {'passed': passed, 'skipped': int(skipped[1]) if skipped else 0,
        'subtests_passed': int(subtests[1]) if subtests else 0, 'raw_summary': summary},
    'product694': {'counts': product['counts'], 'total': 73, 'result_sha256': sha(base/'astra-status-batch694/RESULT.json')},
    'previous_full': 'Interrupted by owner for professor demonstration; raw log preserved, no pass claimed.',
    'model_and_runtime_unchanged': True, 'survey_coverage_added': 0, 'goal_complete': False}
seal(out, out, result, note, [])
state_path = base/'RELEVO_ACTIVO.json'
state = read(state_path)
state.update(activeValidation=None, confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='693adoptada tras Full completo y comparación694 adjudicada; publicar fuente/evidencias en Goal-c03.',
    continuation='Auditar índice, publicar693 y evidencia690–694. Después localizar primera transformación errónea con HTTP694; ampliar estado a29IDs adicionales con contexto recuperado. Mantener742/26cubiertos/716abiertos.',
    previousGoalTurnClassification='progress', previousGoalTurnClassificationReason='Fuente compartida693 validada; todos73resultados694 preservados y mejoras medidas. C03 global sigue abierto.')
write(state_path, state)
matrix = root/'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
lines = matrix.read_text(encoding='utf-8-sig').splitlines()
addition = f' Fuente693: cantidades tipadas y RAM instalada independiente; wifi.status de lectura. Full0: Python{passed}pases/{result["python"]["skipped"]}skips, NET{result["dotnet"]["passed"]}pases/{result["dotnet"]["aggregate_skipped"]}skip agregado, opt-ins aparte. [Producto694](../../../artifacts/comprobaciones/C03/astra-status-batch694/RESULT.md):{product["counts"].get("correct_observed_run",0)}/73correctos en corrida; fallos restantes preservados, encuesta26/716/0 y C03 global abiertos. |'
for index,line in enumerate(lines):
    if line.startswith('| G04.02 /') or line.startswith('| G06.01 /'):
        assert line.endswith('|')
        lines[index] = line[:-1]+addition
matrix.write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'adopted693': True, 'python': result['python'], 'dotnet': result['dotnet'], 'product694': result['product694']}, ensure_ascii=False))
