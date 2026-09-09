from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-account-catalog410'
for name in ['focal', 'python-owners', 'kernel', 'fast']:
    (out / f'{name}.log').write_bytes((Path(os.environ['TEMP']) / f'c03-account-catalog410-{name}.log').read_bytes())
(out / 'RESULT.md').write_text('''# 410 — cuenta Windows conservada en alcance y catálogo

ProductCatalog identifica explícitamente la cuenta Windows del proceso, su
dominio/usuario y la diferencia respecto del nombre humano. Reutiliza exactamente
el descriptor387, cuya utilidad de retrieval408 y decisión409 ahora está medida.
effect_intent deja de tratar una cláusula con cuenta/usuario como estado completo
de recursos/OS. No fuerza identity; la selección normal decide. Las palabras
genéricas identidad/identity del hook405 no se añaden: también describen una GPU.

Validación:
- Baseline focal5failed7passed0skips1,41s; final12passed0skips0,63s.
- Python: `pytest tests/test_effect_intent.py tests/test_effect_intent_state_corpus.py
  tests/test_planner.py -q`:2260passed,121subtests passed,0skips,42,27s.
- `dotnet test tests/Baxy.Kernel.Tests -c Release --nologo -v:minimal`:
  140passed,0reported skips,1s. La salida además menciona el benchmark explícito
  CompareMemoryStreamAndArrayBufferWriterImplementations como omitido; no se cuenta
  como pass ni como validación de rendimiento. Este es un tramo de reparación.
- `scripts/test_source_quality.ps1 -Mode Fast`: verde entero,build10,88s,
  0advertencias/errores. No Full durante reparación.

409 con mente real caliente mejora11/13→13/13. La consulta usernameEN fría sigue
como riesgo concreto: descriptor lexicalrango20 y recuperación closedknowledgetop4.
411 se prepara como producto real sin espera para observar esta frontera y la
composición de observaciones verificadas. No promoción de modelo, UI ni voz física.
''', encoding='utf-8')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = [out / n for n in ['PREREG.json', 'RESULT.md', 'baseline.log', 'focal.log', 'python-owners.log', 'kernel.log', 'fast.log']]
paths += [root / p for p in ['src/baxy_mind/effect_intent.py', 'src/Baxy.Kernel/Operations/ProductCatalog.cs', 'tests/test_effect_intent.py']]
(out / 'PINS.json').write_text(json.dumps({str(p): sha(p) for p in paths}, indent=2) + '\n', encoding='utf-8')
research = '''
## 406–410 — búsqueda de operaciones y cuenta de Windows (2026-09-08)

Herencia: biblioteca/gemma4-agent/documentacion/02_router/research/
07_SKILL_RETRIEVAL_research.md:1–62 y evidencia retrieval270. Se separa selección
de disponibilidad de herramientas. [TinyAgent](https://arxiv.org/abs/2409.00608)
aporta el mecanismo de recuperación local de herramientas; sus cifras no son
resultados de BAXY. La [ficha E5](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md)
mantiene query/passage en recuperación asimétrica y vectores normalizados, ya
usados por router.py. Snapshot614241f6/manifest e1ab2f71 verificado en406b.

407 refuta la hipótesis de promoción bloqueada: semántica disponible24,438s;
antes, lexical.408 demuestra2/4→4/4cuentas visibles al reutilizar descriptor387;
40911/13→13/13decisiones útiles con E5cargado. Se adopta410 descriptor y abstención
de recursos ante cuenta/usuario. No nueva capa/clasificador, catálogo alternativo
ni espera impuesta al usuario. UsernameENfrío permanece fuera del top4: producto411
lo mide. RESULT/PINS406–410 conservan configuración, límites y controles.
'''
with (base / 'INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md').open('a', encoding='utf-8') as stream:
    stream.write(research)
state = '''# C03 — fuente410 validada; producto411 preparado — EN_CURSO

Goal completo activo; Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia. Sin
agentes, commit/push ni Full durante reparación. BAXY manual cerrado; encuesta
742/rev1248 y16mensajes directos consolidados, automáticos excluidos.

Fuente actual410(Python y.NET): scope recursos abstiene ante cuenta/usuario;
ProductCatalog usa descriptorWindows exacto387. No fuerzaidentity ni extrae nombres.
Se excluyen palabras genéricas identidad/identity del hook405 para preservar GPU.
Baseline5fail7pass; focal12pass0skip0,63s; Python3dueñas2260pass+121subtests0skip42,27s;
Kernel140pass0reportedskips1s, benchmark explícito omitido y no contado como pass;
Fastverde/build10,88s0warnings/errors. RESULT/PINS410completos. NoFull.

411 preparado:scratchpad/c03-account-product411.py; seis sintéticos en perfil
C03-account-profile411, observadorHTTP sólo lectura, diagnóstico3.5-4B sinpromoción.
Primero usernameEN frío, luego cuentasES/EN/ES, versiónOS, concepto. Ninguna espera
deE5. Verificar admission, activity, journal, prosa y estado terminal. CuentaWindows
real sólo en captura privadaC03-account-product411-private; no copiar identificador
sin necesidad. Registrar handle al arrancar; no editar/build/otro modelo hasta cierre.

409 mente completa caliente:11/13→13/13 con descriptor exacto387 yscope405 igual
enambos brazos.4cuentas→identity,3recursos→status; concepto/prohibición y4nombres
humanos útiles sinlectura. Álvaro contieneÁ real, noescapevisible.26respuestas,
procesoscerrados,manifiestointacto,RESULT/PINScompletos. NoUI/voz/aceptaciónfresca.
408retrieval2/4→4/4cuentas visibleslex/E5; lexrangos1/1/20/3, E5rangos1/1/1/7.
UsernameENfrío sigue fuera top4 para reabrir knowledge; 411lo observa enproducto.

407 promoción funciona: E5ready20,766s, corpus20,984s, semántica24,438s; warm7/9.
405audit lexical, scope5/9→6/9. No tocar timeout/orden por hipótesis refutada.
406bencoderCPU2/4cuentas visibles (diferentes quelexical),406falló arnésPYTHONPATH;
ambosconservados. InvestigaciónE5/TinyAgent heredada/contrastada yRESULT/PINS405–410.

404nombre genérico usa conversación humana reciente, explícito guardado memoria;
6focal/1905dueñas/Fast17,78s.402valor único corto9focal/186dueñas/Fast18,15s.
404bproducto3útiles1parcial2fallos: T6Álvaro correcto,T4sinfinal,T5Mi nombreJordan.
T4incluye bienvenida ausente402b; noinputidéntico. Abiertas prosa memoriaES/redactada,
falsa persistencia al presentarse, precedencia aclaración sobre lecturaMainWindow671.

No repetir399/400thinking,prompt391,resolvedor392,catálogo376,wrappers346/347,
origen349,9B390 sin dato nuevo. Archivos CHECKPOINT_408_ANTES_409 y400/404.
Resta C03: ocho rutas/encuesta/fallos264;0requisitos finales y0/100frescos certificados;
averías/recuperación, UIreal/vozfísica/ASR/wake/≤4GBconjunto, runtime/instalación/
contratosC04–C09, Fullverde/publicación. Sinbloqueo externo, no cerrar ni inventarETA.
'''
(base / 'CHECKPOINT.md').write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state.replace('# C03', '# Handoff C03', 1), encoding='utf-8')
relevo = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'))
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='Source410 adopted:12focal/2260Python+121subtests/140Kernel/Fast10.88s. Kernel explicit benchmark omitted, not counted.40911/13→13/13 warm.', continuation='411 product prepared,6synthetics with cold usernameEN first. Record handle when launched; no source/build/other model until completion.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('410 recorded;411 prepared')
