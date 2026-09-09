from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-name-scope404'
for name in ['baseline', 'focal', 'focal-final', 'owners', 'fast']:
    target = out / f'{name}.log'
    assert not target.exists()
    target.write_bytes((Path(os.environ['TEMP']) / f'c03-name-scope404-{name}.log').read_bytes())
report = '''# 404 — el nombre actual conserva su contexto de conversación

MainWindowViewModel deja de forzar memory.recall para una consulta genérica del
nombre cuando los últimos doce mensajes contienen una presentación del usuario.
NaturalMemoryRequestParser reconoce ese alcance reutilizando su patrón de
consulta y el de presentación. Sólo consulta mensajes con rol humano; no extrae
un nombre, no crea caché ni concede permiso de escritura. La mente interpreta
las declaraciones y correcciones completas. Las preguntas explícitas sobre lo
guardado y las sesiones sin ese contexto conservan la ruta privada.

403 demuestra la causa con la mente real: ÁlvaroES/EN, Renata y Priya frente a
hermanaCasey correctos; el producto402b había sustituido Álvaro por Jordan guardado.
Los controles de cuentaWindows403 fallan antes del modelo, quedan registrados.

- Baseline App:3failed,3passed,0skips,27s. Los tres recuerdos conversacionales
  hacían una lectura persistente y no llegaban a la mente.
- Primer focal:3failed,3passed,25s. Las garantías de ruta ya pasaban; fallaba una
  comprobación de test que abría un outbox inexistente. Se exige ahora que no
  exista tras conversación sin operaciones; las ramas privadas exigen outbox vacío.
  La lengua de la respuesta del fixture se liga a la presentación inicial.
- Focal final:6passed,0skips,25s.
- `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
  --filter 'FullyQualifiedName~MindShellEndToEndTests|FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~RequestReadingConformanceTests'`:
  1905passed,0skips,5m31s.
- `scripts/test_source_quality.ps1 -Mode Fast`: verde entero, build17,78s,
  0 advertencias/errores. No Full durante reparación.

El fixture de contratos comprueba la ruta y el journal, no la calidad del modelo.
403 conserva esa medición real; producto404b se registra aparte. FuentePython397
intacta; sin cambio del runtime ni promoción. C03 permanece EN_CURSO.
'''
(out / 'RESULT.md').write_text(report, encoding='utf-8')
paths = [out / name for name in ['PREREG.json', 'RESULT.md', 'baseline.log', 'focal.log', 'focal-final.log', 'owners.log', 'fast.log']]
paths += [root / name for name in ['src/Baxy.App/NaturalMemoryRequestParser.cs', 'src/Baxy.App/MainWindowViewModel.cs', 'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs']]
(out / 'PINS.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2) + '\n', encoding='utf-8')

archive = base / 'CHECKPOINT_404_ANTES_PRODUCTO.md'
assert not archive.exists()
archive.write_bytes((base / 'CHECKPOINT.md').read_bytes())
checkpoint = '''# C03 — fuente404 validada / producto404b activo — EN_CURSO

Goal completo activo, Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY manual cerrado.
Encuesta final742/rev1248,16 mensajes directos consolidados; automáticos excluidos.
Original y servidor101140 intactos. No nuevo pedido de confirmación pendiente.

ACTIVO: producto404b, handle74614, scratchpad/c03-product404b.py. Seis turnos
sintéticos idénticos402b en perfil privado nuevo, observadorHTTP sin inyección.
LOCALAPPDATA/BAXY/C03-stored-product404b-private; perfilC03-stored-profile404b.
Recoger antes de editar fuente/build/otro modelo. Resto de modelos y pruebas
cerrados; handles20195,16471,85524,94561,57928 cerrados. Ningún405 preparado.

Última.NET404: consulta genérica de nombre va a mente cuando último12mensajes
contiene cláusula humana de presentación. Reusa DeclaredNameInputPattern y grupo
conversation en NameRecallPattern; sin extraer valor/caché/permiso de escritura.
Explícita guardada y sin contexto mantienen memoria. Baseline3fail3pass27s;
primerfocal3fail3pass25s sólo por abrir outbox inexistente; ahora exige ausencia.
Focalfinal6pass0skip25s; cinco dueñas1905pass0skip5m31; Fast17,78sbuild verde,
0warnings/errors. RESULT/PINS astra-name-scope404 completos. Python sigue397.

402 añade valor único≤256/no redactado de recall/list verificado al contrato
RequiredLiteralFacts existente, tanto composición como aceptación final. Baseline
4fail5pass779ms (aserción Is.Empty→Is.Null también corregida); final9pass444ms,
tres dueñas186pass0skip3m05; Fast18,15sverde.401 real3/8→5/8, sin regresiones;
nombresES siguen sujeto incorrecto y redacción produce vacío en ambos brazos.
401/402 RESULT/PINS completos. No declarar solved toda memoria por este cambio.

402b producto:3útiles en contenido,1parcial,2fallos. T1error/confirmaciónhonestos;
T2guardado real pero prosa genérica; T3leeJordan y lo conservaEN; T4Me llamoÁlvaro
→aclaración innecesaria; T5Jordan correcto por CONVERSACIÓN tras esa aclaración,
NO una nueva lectura privada; T6genérico fuerzaJordan persistido. Journal sólo
dos recall. RESULT/PINS completos,6admissions200,sin timeout/finalausente,exit0.

403 mente completa con historial real402bT6 último12roles:4/6útiles. Los cuatro
recuerdos correctos (ÁlvaroES/EN,Renata,Priya≠hermanaCasey) justifican el scope404.
Dos controles nuevos de cuentaWindows caen en system.status por explicit_effects
antes delLLM. No son los mismos textos387/399. RESULT/PINS completos. Causa
localizada: effect_intent._MACHINE_STATUS_SCOPES/os4389 acepta que/which...Windows
y _machine_status_is_the_whole_clause4475 no excluye lectura de cuenta/usuario.
SystemStatusContracts sólo recursos/OS; userName lo devuelve SystemIdentityHandler.
Posible siguiente comparación: hacer abstener sólo ese scope ante cuenta/usuario
y dejar selector nativo existente; conservar controles de versiónOS/CPU y conceptos.
NO implementado ni preparado405; no añadir prompt ni hardcodear system.identity.

Otras causas abiertas: MainWindowViewModel671 da precedencia a aclaración pendiente
incluso ante ruta privada explícita. DeclaraciónT4: primera nativa402b inventa que
Álvaro está guardado; guardas terminan en aclaración inútil.401redactado recibe
[REDACTED], niega acceso general y acaba vacío tras copied_instruction/internal_code.

Python397: idioma por tilde aislada corregido y frases me llamo/te llamas/se llama
con límites de palabra;21focal/1364dueñas0skip6,14s/Fast1,22sverde. InputJoséEN
sigue metadata mixed.395 conserva historial en retry;3942/5→4/5+parcial frente
a3965/5 con payloads idénticos: variación documentada, no estabilidad certificada.
399/400 thinking512/sampler recomendado rechazados; no semillas/perfiles comparables.
GPU3175,56MiB/RAM≈3906MiB aislado, no voz conjunta. Registro2507 intacto.
No repetir prompt391, resolvedor392, catálogo376, wrappers346/347 ni origen349;
3909B2/4 sin mejora. Historia detallada: CHECKPOINT_400_ANTES_401.md,
CHECKPOINT_404_ANTES_PRODUCTO.md y RESULT/PINS por tramo.

Falta C03 completo: ocho rutas/base encuesta/fallos264;0 requisitos validados
finales y0/100 humanos frescos certificados; averías/recuperación; UI real;
voz física/ASR/wake/recursos conjuntos≤4GB; runtime/instalación/contratosC04–C09
sin ejecutar otros goals; Full final verde y publicación fuera de main.
Sin bloqueo externo ni porcentaje/plazo inventado. No marcar completo/bloqueado.
'''
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
handoff = '''# Handoff C03 — 2026-09-08 — fuente404 validada, producto404b activo

Goal completo activo; Goal-c03/2bf3d4c. Preservar WIP/main/evidencia. Sin agentes,
commit/push ni Full durante reparación. BAXY manual cerrado; encuesta742/rev1248
y16 mensajes directos consolidados, automáticos excluidos. Original/servidor intactos.

ACTIVO: handle74614, scratchpad/c03-product404b.py. Seis sintéticos idénticos402b,
perfil aisladoC03-stored-profile404b, capturaC03-stored-product404b-private.
Recoger antes de editar/build/otro modelo. Resto de modelos y pruebas cerrados.

Última.NET404: consulta genérica de nombre con presentación humana dentro de
último12mensajes usa mente; explícita/sincontexto mantiene lectura privada.
No extrae nombre ni crea caché. Focal6pass0skip25s; cinco dueñas1905pass0skip5m31;
Fast verde/build17,78s0warnings/errors. Primerfocal falló por el test que abría
outbox inexistente; ahora exige ausencia, conservar ambos logs. RESULT/PINS404.
402 retiene valor único corto no redactado de lectura:9focal/186dueñas/Fast18,15s.
Python397 intacta:1364dueñas0skip/Fast1,22s; idioma/tilde y frases con límites.

402b:3útilescontenido1parcial2fallos. T4 presentación→aclaración innecesaria;
T5Jordan correcto por conversación tras esa aclaración, NO nueva lectura;
T6leeJordan persistido en vez del contextoÁlvaro.403 mente responde los cuatro
recuerdos actuales correctamente;2cuentasWindows nuevas mal como system.status
antes delLLM(explicit_effects). RESULT/PINS401–404/402b completos.

Siguiente: adjudicar404b con activity(event.entry), terminales y journal. Después
posible scope de cuentas: effect_intent.py4389/4475 confunde que/which...Windows
con versiónOS; sólo abstener ante la otra lectura y conservar selector nativo,
sin hardcode de operación/prompt. No405 preparado. También quedan precedencia
de aclaración sobre memoria(MainWindow671), falso guardadoT4 y redacción401vacía.

No repetir perfiles399/400, prompt391, resolvedor392, catálogo376, wrappers346/347,
origen349 ni9B390 sin dato nuevo. Modelo registrado2507 intacto; diagnósticos3.5-4B
no son promoción. Techo4GB conjunto, voz/UI aún no certificados.
Cierre restante: ocho rutas/encuesta/fallos264;100humanos frescos0certificados;
averías,UI/voz física,recursos/runtime/instalación/contratos,Fullverde/publicación.
CHECKPOINT.md manda; no cerrar goal ni declararlo bloqueado.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8-sig'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
             checkpoint='404 validated6focal/1905owners0skip5m31/Fast17.78s.402 observed literal retained; Python397 intact.4034/6 with two existing Windows-account scope failures.',
             continuation='Product404b active handle74614; collect before source/build/new model. No405 prepared. Full C03 active.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
