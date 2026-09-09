"""Preserve the failed combined gate and pin the foreground regression repair."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(source[:source.index("out = base/'astra-gemma-product614'")], __file__, 'exec'))
temp = Path(os.environ['TEMP'])
out = base/'astra-context-source646'
assert not (out/'RESULT.json').exists()
full = (out/'FULL_RED.log').read_text(encoding='utf-8-sig')
assert '24 failed, 10371 passed, 3 skipped, 466 subtests passed' in full
assert (temp/'c03-context646-full-exit.txt').read_text().strip() == '1'
for original, target in [('c03-context646-fast.log', 'FAST.log'), ('c03-context646-pins.log', 'DECLARATIONS.log')]:
    (out/target).write_bytes((temp/original).read_bytes())
result = {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': False,
          'full_exit': 1, 'python': {'failed': 24, 'passed': 10371, 'skipped': 3, 'subtests': 466, 'seconds': 681.93},
          'dotnet_passed': 4469, 'dotnet_aggregate_skipped': 1, 'dotnet_printed_omissions': 16,
          'owners_passed': 3505, 'owners_subtests': 121, 'targeted_passed': 50,
          'sources': read(out/'PREREG.json')['sources'], 'repair_campaign': 651,
          'regression_origin': 'd5757c69 (633), before contextual646; all24 exact operation oracles pass at parent and fail at633 and641.',
          'goal_complete': False}
note = '''# 646: Full rojo conservado; fuente combinada pendiente

Python: 24 fallos, 10371 pases, 3 skips y 466 subpruebas (681,93 s). .NET: 4469 pases, 1 skip agregado y 16 omisiones opt-in impresas por separado. Las dueñas3505 y50focales habían pasado, pero no bastaron: no se adopta el conjunto C#+Python con este resultado.

Los fallos pertenecen a R4(2), R5(8) y R6(14). Los24oráculos originales pasan antes de d5757c69 y fallan desde ese commit633 y en641. Se perdieron sinónimos de primer plano y lecturas singulares dentro de enumeraciones al restringir el alcance de ventana. La referencia contextual646 no es la primera transformación que los rompe.651 repara y vuelve a validar el conjunto; este rojo no se reescribe como verde.

647 conserva18/20finales, incluidas4referencias recuperadas, pero falta la prosa veraz y el idioma. Encuesta25cubiertos/717abiertos/0NA. No cierre deC03 ni crédito deUI/voz conjunta.
'''
seal(out, home, result, note, [])

out = base/'astra-window-regression651'
files = {p.relative_to(root).as_posix(): p for folder in ['experiments/voice_latency', 'scripts', 'src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest = hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree = digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py', 'evaluate_reserved_stt.py']:
    p = root/'experiments/stt_quality'/name
    data = p.read_bytes()
    old = b'9d8f2af82e91f1565668a3c1af9ec155a7424ffcd58a053da3ce0f0797edf590'
    assert data.count(old) == 1
    p.write_bytes(data.replace(old, tree.encode()))
for original, target in [('c03-window651-r456.log', 'INTERMEDIATE_RED.log'), ('c03-window651-r456-final.log', 'R456.log'), ('c03-window651-scope.log', 'SCOPE.log'), ('c03-window651-owners.log', 'OWNERS.log')]:
    (out/target).write_bytes((temp/original).read_bytes())
assert '3521 passed' in (out/'OWNERS.log').read_text(encoding='utf-8-sig')
write(out/'SOURCE.json', {'utc': datetime.now(timezone.utc).isoformat(),
    'sources': {name: sha(root/name) for name in [*read(out/'PREREG.json')['baseline_sources'], 'tests/test_effect_intent.py', 'tests/test_window_query_context.py']},
    'python_tree_sha256': tree, 'r456_passed': 1408, 'scope_passed': 97,
    'owners_passed': 3521, 'owners_subtests': 121, 'owners_skipped': 0,
    'criteria': 'Fast/Full still required;646 remains sealed red, adoption of corrected combined source recorded only in651.'})
state = read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='646sellado rojo;651repara24regresiones633. R4561408pass,97scope,3521dueñas+121subtests/0skips. Fast/Full pendientes.25/717/0.',
    continuation='Validar pins/Fast/Full651; no ejecutar cierre646 obsoleto (646 quedó sellado rojo). Fuente congelada durante Full; después publicar conjunto validado y continuar prosa649/650.',
    activeValidation=None)
write(base/'RELEVO_ACTIVO.json', state)
print({'sealed646': 'red_not_adopted', 'source651_tree': tree, 'owners_passed': 3521})
