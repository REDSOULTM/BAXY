from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-account-scope405'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-account-scope405-private'
rows = [json.loads(s) for s in (out / 'replies.jsonl').open(encoding='utf-8')]
cases = json.loads((root / 'scratchpad/c03-account-scope405-cases.json').read_text(encoding='utf-8'))['cases']
expected = {c['id']: c for c in cases}
report = ['# 405 — abstención de alcance: mejora parcial, no adoptada', '',
          'Nueve sintéticos por brazo: 5/9 útiles en baseline y 6/9 con la abstención de cuenta/usuario. Sin regresión útil; tres fallos persisten. No edición de fuente, promoción, ejecución de operaciones ni aceptación humana fresca.', '',
          'La cuenta en inglés pasa de system.status a system.identity. Las dos consultas de cuenta en español carecen de system.identity entre los 28 candidatos: una propone system.process.list y termina unsupported; la otra no propone operación. El username inglés sigue como explicit_conversation, con una falsa negación de acceso al PC. OS, RAM, CPU, concepto y prohibición se conservan.', '',
          'La falta de candidatos no demuestra por sí sola que E5 esté inactivo. Se investigará la búsqueda existente y su readiness antes de cambiar descriptores o reglas. El hello sólo nombra E5, no acredita que haya promovido el catálogo.', '',
          'Ambos sidecars cerraron; manifiesto intacto. Sin medición nueva de RAM/VRAM. hello.json fue sobrescrito por el segundo brazo; stderr separado. No repetir para esconder esta limitación.', '']
for row in rows:
    reply = row['reply']
    report += [f"## {row['variant']} / {row['id']}", '', expected[row['id']]['request'], '',
               f"Tipo: {reply['kind']}; operación: {reply.get('operation')}; {row['seconds']} s.", '',
               '> ' + (reply.get('reply') or reply.get('question') or '(sin prosa: propuesta estructurada)').replace('\n', '\n> '), '']
assert not (out / 'RESULT.md').exists()
(out / 'RESULT.md').write_text('\n'.join(report), encoding='utf-8')
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'replies.jsonl', 'EXIT.json', 'PROCESS-baseline.json', 'PROCESS-identity-scope.json']]
paths += [private / n for n in ['catalog.json', 'http-posts.jsonl', 'turn-audit.jsonl', 'hook/sitecustomize.py', 'hello.json', 'stderr-tail-baseline.json', 'stderr-tail-identity-scope.json']]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')

product = base / 'astra-stored-product404b'
diff = json.loads((product / 'payload-diff.json').read_text(encoding='utf-8'))
a, b = diff['messages402b'], diff['messages404b']
systems_equal = [m for m in a if m['role'] == 'system'] == [m for m in b if m['role'] == 'system']
note = ('\n## Comparación posterior de los payloads T4\n\n'
        f'Campos distintos de messages iguales; mensajes system iguales: {systems_equal}. '
        '404b incluye la bienvenida inicial como mensaje assistant; 402b no la incluye. '
        'La diferencia entre aclaración y final ausente no es una variación con payload idéntico. '
        'No se atribuye a la nueva selección de alcance404. Véase payload-diff.json.\n')
with (product / 'RESULT.md').open('a', encoding='utf-8') as stream:
    stream.write(note)
pins = json.loads((product / 'PINS.json').read_text(encoding='utf-8'))
for p in [product / 'RESULT.md', product / 'payload-diff.json']:
    pins[str(p)] = sha(p)
(product / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')

state = '''# C03 — fuente404 validada; producto404b y diagnóstico405 cerrados — EN_CURSO

Goal completo activo; Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY manual cerrado.
Encuesta742/rev1248 y16 mensajes directos consolidados; automáticos excluidos.
Original/servidor101140 intactos. Ningún modelo/producto/test activo al cerrar405.

Fuente.NET404: nombre genérico con presentación humana reciente va a conversación;
consulta explícita guardada/sin contexto conserva memoria privada. Sin caché ni
extracción de nombre. Focal6pass0skip25s; cinco dueñas1905pass0skip5m31;
Fastverde/build17,78s0warnings/errors. Python397 intacta1364dueñas0skip/Fast1,22s.
402 conserva valor único corto no redactado:9focal/186dueñas/Fast18,15s.

404b producto6sintéticos:3útiles1parcial2fallos. T6respondeÁlvaro conversacional
en vez deJordan persistido. T4Me llamoÁlvaro agota composición sin final;
T5lectura privada diceMi nombreJordan(sujeto incorrecto).6admissions200,1final
ausente/composition_failed,sin timeout,exit0,manifiesto intacto. No mejora global.
Su primer payloadT4 incluye bienvenida assistant ausente402b: NO input idéntico.
RESULT/PINS404b completos con payload-diff. No atribuir esa variación al scope404.

405 dos sidecars secuenciales/nueve sintéticos:5/9→6/9 al hacer abstener sólo
machine-status ante cuentas/usuarios. No adoptado. CuentaEN→identity correcto;
dos cuentasES→unsupported sin identity entre28candidatos; usernameEN cae antes
delLLM en explicit_conversation y niega acceso. OS/RAM/CPU/concepto/prohibición
se conservan. RESULT/PINS405 completos; no recursos propios nuevos ni promoción.

Siguiente: diagnóstico406 de retrieval existente en CPU, mismo catálogo405 y
consultas, lexical frente a E5 cargado; medir readiness/rangos antes de inferir
que la promoción falla. La ausencia de identity NO prueba E5 inactivo. Startup
__main__7290 espera corpusbuilding dentro de185s, luego promueve; router.py427,
885 y turn_evidence.py1388. Existe SemanticEncoderCPU local con snapshot físico
fijado. Herencia07_SKILL_RETRIEVAL_research y evidencia270; E5 query/passage ya
correctos. No descriptor ni hardcodeidentity, no fuente405/406, no nuevo perfil.

Otros abiertos: prosa de memoriaES/redactada y falsa persistencia al presentarse;
aclaración pendiente tiene precedencia sobre lectura explícita(MainWindow671).
No repetir399/400thinking, prompt391, resolvedor392, catálogo376, wrappers346/347,
origen349 ni9B390 sin dato nuevo. Histórico CHECKPOINT_404_ANTES_PRODUCTO.md y
CHECKPOINT_400_ANTES_401.md; RESULT/PINS401–405 y402b/404b completos.

Resta C03 completo: ocho rutas/encuesta/fallos264;0requisitos finales validados,
0/100humanos frescos certificados; averías/recuperación, UIreal, vozfísica/ASR/wake,
recursosconjuntos≤4GB, runtime/instalación/contratosC04–C09, Fullverde/publicación.
Sin bloqueo externo ni porcentaje/plazo inventado. No marcar completo/bloqueado.
'''
(base / 'CHECKPOINT.md').write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state.replace('# C03 —', '# Handoff C03 —', 1), encoding='utf-8')
relevo = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='404 validated; 404b3useful1partial2fail; 4055/9→6/9 partial not adopted. All processes closed except questionnaire.', continuation='406 retrieval-only lexical/E5 diagnosis next. No source405/406. Full C03 active.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'405_rows': len(rows), '404b_systems_equal': systems_equal, 'state_updated': True}))
