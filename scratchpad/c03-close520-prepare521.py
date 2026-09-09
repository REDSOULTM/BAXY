"""Seal the factual narration fix, prepare real regression, and record upstream delta."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,difflib

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-status-evidence520';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-status-evidence520-private'
assert '3406 passed, 121 subtests passed in 52.67s' in (out/'owners.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (out/'fast.log').read_text(encoding='utf-8-sig')
source=root/'src/baxy_mind/llm.py'
(out/'SOURCE.patch').write_text(''.join(difflib.unified_diff((private/'llm.py').read_text(encoding='utf-8-sig').splitlines(keepends=True),source.read_text(encoding='utf-8-sig').splitlines(keepends=True),fromfile='a/src/baxy_mind/llm.py',tofile='b/src/baxy_mind/llm.py')),encoding='utf-8')
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(source),'change':'Only remove the broad second sentence about PC changes from the successful-status shape instruction. Verified-results instruction, all evidence, validators, model and profile remain. No additional layer/generation or fixed visible reply.','owners':{'passed':3406,'subtests_passed':121,'skips':0,'seconds':52.67,'session':89617,'exit':0},'fast':{'passed':True,'release_seconds':2.90,'warnings':0,'errors':0,'session':75292,'exit':0},'causal_baseline':'519 paired product8/11→9/11 with only hint removal; T2 andT11 remain failures.','limits':'No Full during repair; actual registered product521 still pending. No physicalUI/voice/acceptance credit.'})
(out/'RESULT.md').write_text('''# Narración de resultados: eliminación de una inferencia inducida

Se elimina sólo la frase genérica sobre cambios en el PC. El redactor conserva la instrucción de informar resultados verificados, junto con todos los datos y guardas. La comparación519 había eliminado así la afirmación no observada de cambios detectados enT9, sin corregir artificialmente las respuestas.

Siete suites Python:3406 pruebas y121 subpruebas aprobadas, cero skips,52,67s (sesión89617exit0). Fast completo y Release2,90s, cero advertencias y errores (75292exit0). Servidores de compilación apagados. La diferencia frente a fuente512 está en SOURCE.patch; C#516 se conserva.521 comprobará la adopción con el producto y registro reales, sin hook de tratamiento. T2/progreso y distinción capacidad-activación siguen abiertos; C03 continúa activo.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
script=(root/'scratchpad/c03-private-product519-base.py').read_text(encoding='utf-8-sig').replace('519-base','521')
start=script.index("    'production_verification':");end=script.index("    'profile_inheritance':",start)
script=script[:start]+"    'production_verification': '521 real product: source520 shape hint removal, C#516 qualified memory configuration, registered Qwen/b9980. Same11cases as519; observation only.',\n    'method': 'Confirm T9 actual disable without unsupported PC claims, prior8controls, clock and private status. T2 andT11 known failures remain failures unless actually resolved. No treatment, sampler/model change, UI or voice.',\n"+script[end:]
target=root/'scratchpad/c03-private-product521.py';assert not target.exists();target.write_text(script,encoding='utf-8')
hook=root/'scratchpad/c03-owner521-hook';hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner517-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('517','521'),encoding='utf-8')
campaign=base/'astra-product-check521';campaign.mkdir(exist_ok=False)
write(campaign/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Same11 actual product requests as519, new isolated private profile, registered model/config, current source520 after owners/Fast. Only observation hook. All synthetic development cases, no reserve.','criteria':'Actual disabled memory and truthful T9; earlier name/confirmation/clarification/recall controls retained; clock verified from own run; no false denial of existing local memory inT11. T2 internal narration remains a known failure. Capture all activities/progress and finals; no count based on admission alone.','resource_limits':'GPU3800MiB/freeRAM768MiB/240s, only owned hidden process tree; no source edits during run.'})
upstream=base/'astra-backend-refresh522'
write(upstream/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'stable':'v0.4.0,5266f24/b10809, latest stable unchanged','nightly':'b10867/f3f1a8f2760f28325a5ec20c05b171e5b7c83a29','previously_evaluated_nightly':'b10865/d4389a4dd920d24c9592f1dc3badbd69be23bd09','delta':'Two commits only: MSVC/clang ARM NEON initializer condition; lazy AUTO falls back OFF when any selected device lacks mmap support.','applicability':'Static inspection: ARM NEON branch is outside this Windows x64 build. CUDA at the exact new commit advertises mmap_support for every non-IGPU device; current RTX3060Laptop is discrete. Explicit lazy ON also does not enter the new AUTO branch. No expected behavioral change for the observed CUDA/profile paths; this is code-based applicability, not a b10867 runtime benchmark.','decision':'No new binary/model download or redundant battery from this delta. Keep tested backend evidence and registered candidate unchanged; reconsider if selecting an iGPU or other unsupported-mapping device.','sources':['https://github.com/ggml-org/llama.cpp/releases/tag/v0.4.0','https://github.com/ggml-org/llama.cpp/releases/tag/b10867','https://github.com/ggml-org/llama.cpp/compare/d4389a4dd920d24c9592f1dc3badbd69be23bd09...f3f1a8f2760f28325a5ec20c05b171e5b7c83a29'],'changes_to_local_runtime':False})
(upstream/'RESULT.md').write_text('''# Revisión posterior de llama.cpp

La publicación estable sigue siendo[v0.4.0/b10809](https://github.com/ggml-org/llama.cpp/releases/tag/v0.4.0). Apareció[b10867](https://github.com/ggml-org/llama.cpp/releases/tag/b10867) después de la b10865 ya evaluada.

El[delta exacto](https://github.com/ggml-org/llama.cpp/compare/d4389a4dd920d24c9592f1dc3badbd69be23bd09...f3f1a8f2760f28325a5ec20c05b171e5b7c83a29) sólo contiene dos cambios: una condición de compilador en ARM NEON, y desactivar carga diferida AUTO cuando algún dispositivo seleccionado no admite mmap. La fuente CUDA del mismo commit anuncia mmap para dispositivos distintos de IGPU. La RTX3060Laptop usada aquí es discreta y la compilación es x64; además la rama nueva no cambia lazy ON explícito.

Por inspección del código, esos cambios no deberían alterar los perfiles CUDA observados. Esto no es una medición de b10867 ni una afirmación sobre otros dispositivos. No hay una causa nueva para descargar y repetir toda la batería en esta máquina; registro, binarios y modelos permanecen intactos. Si se elige una iGPU u otro backend sin mmap, esta revisión sí será pertinente.
''',encoding='utf-8')
write(upstream/'PINS.json',{p.name:sha(p) for p in upstream.iterdir() if p.is_file() and p.name!='PINS.json'})
note='\n520 validado: siete owners3406pass+121subtests/0skips52,67s(89617exit0);Fast75292exit0,Release2,90s0warnings/errors. Buildservers apagados. Fuente llm520 elimina sólo frase genérica; C#516 intacto.521 preparado sin tratamiento,11casos producto519.522 refresco upstream cerrado: estableb10809, nocturnab10867 añade dos cambios ARMNEON/lazyAUTOsinmmap; CUDA RTXdiscreta no debería activar esa diferencia, inferencia de código, no benchmark ni promoción. Siguiente número libre523.\n'
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8') as f:f.write(note)
relay_path=base/'RELEVO_ACTIVO.json';relay=json.loads(relay_path.read_text(encoding='utf-8-sig'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='520 validado3406+121/Fast; C#5161962/Fast.522 upstream cerrado;521 preparado.',continuation='Ejecutar521 y adjudicar. Después T2 resultados, capacidad/activación y progreso; reserva518/exposición/contexto; C03 íntegro activo.');write(relay_path,relay)
print('520 and522 closed;521 product ready; no runtime processes active.')
