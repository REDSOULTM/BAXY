from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out408 = base / 'astra-retrieval-descriptor408'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(out408 / 'RESULT.md').write_text('''# 408 — descriptor heredado mejora visibilidad, no demuestra decisión

Mismo descriptor exacto387. Cuatro consultas de cuenta:2/4→4/4 visibles tanto
lexical como E5. Semantic rangos1/1/1/7; lexical1/1/20/3. Tres controles de recursos
conservan status. La consulta usernameEN fría sigue fuera del top4 usado para
reabrir respuestas de conocimiento; esto permanece como riesgo concreto.

E5 CPU20,000s, recursos3,219s; ningún LLM, operación, fuente o perfil modificado.
La frase heredada del método PREREG «no synonyms» describe baseline, no los brazos
descriptor: new_description y new_evidence registran explícitamente la diferencia.
No se altera PREREG después de medir. Reutilizar387 ahora se justifica por la
ausencia de candidatos406/407; su fallo de selección387 permanece válido.
''', encoding='utf-8')
paths = [out408 / n for n in ['PREREG.json', 'ranks.jsonl', 'READINESS.json', 'RESULT.md', 'EXIT.json']]
(out408 / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')

cases = json.loads((root / 'scratchpad/c03-account-scope405-cases.json').read_text(encoding='utf-8'))['cases']
cases += [c for c in json.loads((root / 'scratchpad/c03-generic-mind403-cases.json').read_text(encoding='utf-8'))['cases'] if not c['id'].startswith('account-')]
case_path = root / 'scratchpad/c03-descriptor-mind409-cases.json'
assert not case_path.exists()
case_path.write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
source = (root / 'scratchpad/c03-retrieval-startup407.py').read_text(encoding='utf-8')
for a, b in [('astra-retrieval-startup407', 'astra-descriptor-mind409'), ('C03-retrieval-startup407-private', 'C03-descriptor-mind409-private'), ('catalog407', 'catalog409'), ('close407', 'close409'), ('c03-account-scope405-cases.json', 'c03-descriptor-mind409-cases.json')]:
    source = source.replace(a, b)
source = source.replace('import hashlib\n', 'import hashlib\nimport copy\n')
source = source.replace("hook_source += (root / 'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8')", "hook_source += (root / 'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8').replace(\"Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private/startup-observer.jsonl'\", \"Path(os.environ['BAXY_C03_STARTUP_AUDIT'])\")")
source = source.replace("prereg = {'utc':", "replacement = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity-scope387/PREREG.json').read_text(encoding='utf-8'))['new_description']\nprereg = {'new_description': replacement, 'utc':")
method = 'Thirteen fixed synthetic development cases: nine405 plus four personal-name controls403. Two sequential full sidecars with the same scope-abstention405 in both, same model/history/sampler. Only system.identity description differs (exact387). Both wait for their own observed semantic resources. No effects, source edit, forced operation, response injection, model promotion or fresh-human acceptance. Cold usernameEN remains a separately known concern from408; this run tests loaded E5.'
reason = '408 demonstrates descriptor improves four account targets from2/4 to4/4 visible.407 full warm mind is7/9. Compare actual decisions, while retaining four name-context controls to detect account/personal-name confusion. Existing primary native-tool and E5 mechanism research applies.'
criteria = 'All four account reads select identity, three resource reads select status, concept/prohibition and four current-name questions remain no-effect and useful; inspect every draft and audit. No gain credited for false refusal, silence, wrong subject, false persistence or mere visibility.'
source = '\n'.join('    '+repr(k)+': '+repr(v)+',' if (k := next((key for key in ['method', 'reason', 'criteria'] if line.startswith('    '+repr(key)+':')), None)) and (v := {'method': method, 'reason': reason, 'criteria': criteria}[k]) else line for line in source.splitlines()) + '\n'
source = source.replace("for variant in ['identity-scope']:\n    env['BAXY_C03_SCOPE405'] = variant", "for variant in ['baseline', 'descriptor']:\n    env['BAXY_C03_SCOPE405'] = 'identity-scope'\n    env['BAXY_C03_STARTUP_AUDIT'] = str(private / f'startup-{variant}.jsonl')\n    current_capabilities = copy.deepcopy(capabilities)\n    if variant == 'descriptor':\n        next(c for c in current_capabilities if c['name'] == 'system.identity')['description'] = replacement\n    (private / f'catalog-{variant}.json').write_text(json.dumps(current_capabilities, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')")
source = source.replace("'capabilities': capabilities}\n", "'capabilities': current_capabilities}\n")
source = source.replace("private / 'hello.json'", "private / f'hello-{variant}.json'")
source = source.replace("private / 'startup-observer.jsonl'", "private / f'startup-{variant}.jsonl'")
for name in ['evidence-initial', 'evidence-after', 'wait']:
    source = source.replace("out / '" + name + ".json'", "out / f'" + name + "-{variant}.json'")
target = root / 'scratchpad/c03-descriptor-mind409.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')

state = '''# C03 — fuente404 validada; comparación409 preparada — EN_CURSO

Goal completo activo, Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia. Sin
agentes, commit/push ni Full durante reparación. BAXY manual cerrado; encuesta
742/rev1248 y16 mensajes directos consolidados, automáticos excluidos.

409 preparado: scratchpad/c03-descriptor-mind409.py. Trece sintéticos (nueve405
ycuatro nombres403), baseline/descriptor387 con la misma abstención405, esperando
E5en ambos. Registrar handle al arrancar, recoger antes de editar/build/otro modelo.
No fuente405–409 ni promoción. Última.NET404/Python397; validaciones abajo.

407 refuta bloqueo de promoción: E5ready20,766s, corpus20,984s, semántica24,438s.
405 sí fue lexical(audit). EsperandoE5 y scope405:7/9vs6/9frío. CuentaES/ENcorrecta,
usernameENniega acceso por explicit_conversation, usernameESelige status. No tocar
timeout/orden de arranque con la hipótesis refutada.406b sólo retrieval:2/4cuentas
visibles con lexical y2/4conE5, distintas. Fallo406fue arnés sinPYTHONPATHhijo,
corregido406b; ambos conservados. RESULT/PINS406/406b/407 completos.

408 reutiliza descripción exacta387:2/4→4/4cuentas visibles lexical/E5; rangos
lex1/1/20/3, semantic1/1/1/7. RecursosOS/RAM/CPU visibles. No decisión acreditada.
Dato nuevo respecto387: faltaban herramientas, no sólo mala selección.409 compara
decisiones reales y conservación de nombres humanos. UsernameENfrío sigue fuera
del top4 de recuperación: limitación abierta, no esperar que409caliente la cierre.
RESULT/PINS408 completos. Primarias E5READMEquery/passage/normalización y TinyAgent;
herencia07_SKILL_RETRIEVAL_research/evidencia270, sin nueva búsqueda general.

404.NET: nombre genérico con presentación humana reciente→conversación; explícito
guardado/sincontexto→memoria.6focal/1905dueñas0skip5m31/Fast17,78s0warn/error.
402valor único corto no redactado:9focal/186dueñas/Fast18,15s. Python3971364dueñas
0skip/Fast1,22s.404b6sintéticos3útiles1parcial2fallos: T6Álvaro correcto; T4sinfinal;
T5Mi nombreJordan(sujeto). PayloadT4tiene bienvenida ausente402b; noinputidéntico.
405scope5/9→6/9parcial noadoptado. RESULT/PINS401–408/402b/404b completos.

Otros abiertos: falsa persistencia al presentarse; memoriaES/redactada; aclaración
pendiente antes de lectura explícita(MainWindow671). No repetir399/400thinking,
prompt391,resolvedor392,catálogo376,wrappers346/347,origen349,9B390 sin dato nuevo.

Falta C03 completo: ocho rutas/encuesta/fallos264,0requisitos finales validados y
0/100frescos certificados; averías/recuperación, UIreal/vozfísica/ASR/wake/≤4GB
conjunto, runtime/instalación/contratosC04–C09, Fullverde/publicación. No cerrar
goal ni declararlo bloqueado; sin porcentaje/plazo inventado.
'''
(base / 'CHECKPOINT_408_ANTES_409.md').write_text(state, encoding='utf-8')
(base / 'CHECKPOINT.md').write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state.replace('# C03', '# Handoff C03', 1), encoding='utf-8')
relevo = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='408 descriptor improves retrieval2/4→4/4.407 warm7/9. Source404/.NET397/Python unchanged.', continuation='409 prepared, compare13cases in2 sequential warm sidecars; record running handle. No source edits while active.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'409_cases': len(cases), 'prepared': True}))
