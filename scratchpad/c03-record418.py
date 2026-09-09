from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-private-precedence418'
for name in ['owners', 'fast']:
    shutil.copyfile(Path(os.environ['TEMP']) / f'c03-memory418-{name}.log', out / f'{name}.log')
assert 'source_quality_gate_passed: mode=Fast' in (out / 'fast.log').read_text(encoding='utf-8-sig')
report = '''# 418 — precedencia privada corregida; owners y Fast verdes

La solicitud privada de memoria ya reconocida por el parser sustituye la
aclaración pública pendiente. Se reutiliza la ruta/contrato privado existente;
NoRoute y AskToSave conservan el flujo mental. Sin nueva operación, persistencia
implícita, capa, frase fija ni cambio de modelo. Diagnóstico y herencia en
DIAGNOSTICO.md. Se preserva el resto del WIP en MainWindowViewModel y tests.

`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~ExplicitPrivateMemoryRequestSupersedesMindClarification|FullyQualifiedName~PrivateMissingValueReplacesPublicClarificationWithoutInventingIt'`
→ 6 pass / 0 skips, 26 s.

`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~MindShellEndToEndTests|FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~PlannerAppBoundaryTests'`
→ 2007 pass / 0 skips reportados, 6 min 51 s. La salida señala además la prueba
explícita OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations como
omitida; no cuenta como pass ni acredita runtime real, UI o voz física. Su
compuerta separada sigue pendiente para el candidato final. Las indicaciones
de latencia de esta suite excluyen composición LLM: no son latencia del producto.

`.\\scripts\\test_source_quality.ps1` → Fast verde completo, build 18,01 s,
0 warnings/errors. No Full durante reparación. Servidores de build inactivos
cerrados mediante build-server shutdown en ambos SDK, sin producto/modelo
activo ni cambio de aplicaciones del usuario. La encuesta permanece abierta.

Producto419 preparado: ocho sintéticos, misma secuencia404b con una petición
de aplicación sin nombre antes de cada lectura privada. Capturará hechos y
finales, comprobará que realmente quedó una aclaración y medirá el árbol del
diagnóstico. Corte conservador VRAM 3800 MiB/RAM disponible 768 MiB, sólo ese
árbol; no certifica el conjunto físico de voz. Falta ejecutarlo y adjudicarlo.
'''
(out / 'RESULT.md').write_text(report, encoding='utf-8', newline='\n')
paths = [out / n for n in ['RESULT.md', 'DIAGNOSTICO.md', 'baseline.log', 'fixture-failure.log', 'focal.log', 'owners.log', 'fast.log']]
paths += [root / n for n in ['src/Baxy.App/MainWindowViewModel.cs', 'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs', 'scratchpad/c03-private-product419.py', 'scratchpad/c03-owner419-hook/sitecustomize.py']]
(out / 'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+'\n', newline='\n')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    p = base / name
    text = p.read_text(encoding='utf-8').replace('memoria418 en validación', '418 validado; producto419 preparado')
    text = text.replace('Owners de memoria/aclaración en curso; después Fast.', 'Owners 2007 pass/0 skips reportados/6m51, más gate runtime explícito omitido\n(no cuenta). Fast verde/build18,01 s/0 warnings/errors. RESULT/PINS418 completos.')
    text = text.replace('Cerrar servidores de compilación inactivos antes para liberar su RAM; encuesta\nno se toca.', 'Servidores de compilación inactivos ya cerrados en ambos SDK; encuesta\nintacta. Usar Python del runtime para419, porque el sampler necesita psutil.')
    p.write_text(text, encoding='utf-8', newline='\n')
p = base / 'RELEVO_ACTIVO.json'
relay = json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), checkpoint='Source418 validated: focal6, owners2007 plus explicit runtime gate omitted, Fast green. Models closed.', continuation='Run prepared product419 with runtime Python and resource guard, then adjudicate all8, private dispatch and remaining prose. Full C03 active.')
p.write_text(json.dumps(relay, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print('418 recorded; product419 next')
