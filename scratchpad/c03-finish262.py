"""Preserve the retrieval diagnosis and the verified application-catalog repair."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-app-catalog262'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY'
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

result = read(out/'CORE_RESULT.json')
assert result['capabilitiesUnchanged'] and result['addedNames']==['Steam']
assert result['removedNames']==[] and result['resolution']['abre steam']=='Steam'
logs = ['c03-app-catalog262-tests.log','c03-app-catalog262-tests-final.log',
        'c03-app-catalog262-fast.log','c03-core262.log','c03-retrieval261.log']
for name in logs:
    shutil.copyfile(Path(os.environ['TEMP'])/name, out/name)
fast = (out/'c03-app-catalog262-fast.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in fast
report = '''# C03 — Steam desaparecía del catálogo: tramos261–262

## Causa demostrada

Los tres textos literales de UI260 se reprodujeron sólo en retrieval, con el
Core actual y el E5 fijado, sin ejecutar operaciones ni LLM. `app.open` ocupó
puestos semánticos116,15,26 para «Tengo en mente que abras steam», «abre steam»
y «Si, abre steam». La primera shortlist coincide exactamente con UI260:
la operación no llegó al selector. Es un problema de recuperación independiente.

Además, el hello de Core exponía292 aplicaciones y ninguna llamada Steam.
Get-StartApps devolvió dos Steam con AppID distintos. Shell AppsFolder expuso:

| Identidad | Destino observado | Estado local |
|---|---|---|
| Valve.Steam.Client | D:\\Steam\\steam.exe | Existe,5.775.512bytes. |
| {7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}\\Steam\\Steam.exe | C:\\Program Files (x86)\\Steam\\Steam.exe | No existe. |

CreateCatalogSnapshot eliminaba cualquier nombre con más de un AppID, y el
resolver también rechazaba esa ambigüedad. El duplicado antiguo ocultaba la
instalación utilizable. No se borró ni modificó ningún acceso directo.

## Contraste y reparación mínima

Se conservó Get-StartApps y la validación de identidades heredada. La alternativa
de elegir la primera coincidencia permitiría ejecutar una instalación incorrecta:
se descartó. Microsoft documenta AUMID como identidad de lanzamiento y
System.Link.TargetParsingPath como destino Shell; no se dedujo una ruta del AppID.
Consulta2026-09-07:

- https://learn.microsoft.com/en-us/windows/configuration/store/find-aumid
- https://learn.microsoft.com/en-us/windows/win32/properties/props-system-link-targetparsingpath
- https://devblogs.microsoft.com/oldnewthing/20251219-00/?p=111885

Sólo para nombres duplicados, WindowsInstalledApplicationPlatform añade el
destino informado por Shell. Conserva una identidad únicamente si tiene un
ejecutable local existente y todas las identidades alternativas tienen destinos
locales comprobados como ausentes. Dos destinos existentes, metadatos desconocidos,
red, instaladores MSI, directorios y acceso denegado no resuelven la ambigüedad.
No equivale File.Exists=false a ausencia: sólo FileNotFound/DirectoryNotFound
con raíz local disponible aportan esa evidencia. El filtro vive en la lectura
del provider, compartida por publicación, resolución y ejecución.

## Validación

`dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal
--filter FullyQualifiedName~WindowsInstalledApplicationOpenProviderTests`:
primera tanda38pass/0skips; final39pass/0skips,108ms. Se añadió protección de
ruta inválida antes de la tanda final. Controles con nombres ajenos a Steam:
destino presente/ausente,ambos presentes,desconocido,ambos ausentes,misma identidad,
URL/ruta remota/directorio y archivos temporales reales. La publicación del
catálogo y el resolver se comprueban conjuntamente.

`scripts/test_source_quality.ps1`: Fast completo verde; Release22,27s,
0advertencias/errores. No Full durante reparación.

Nuevo hello del Core Release reconstruido: **293 nombres, único añadido Steam,
ningún nombre retirado y169 operaciones idénticas**. «abre steam» resuelve a
Steam. `CORE_RESULT.json` conserva huellas de Core y provider. Esta es lectura
de catálogo, todavía no una prueba de abrir/enfocar Steam desde la UI nueva.

## Pendiente causal, no ocultarlo

La corrección de identidad no cambia retrieval. «Tengo en mente que abras steam»
sigue sin identidad extraída por resolve_application_catalog_app_id, y `app.open`
continúa fuera del top28 calculado261. «Si, abre steam» también devuelve null en
ese helper aislado; eso no prueba toda la ruta contextual. Se deben comparar los
recorridos integrados, sin añadir prefijos por frase ni promover esta reparación
como C03 completo. También queda la generalización falsa de capacidades tras un
fallo previo, observada en UI260. Reserva100/100 aún sin congelar.

Sesiones63898(261),98309(38tests),26242(39tests/Fast) terminales exit0 recogidas.
Core262 lectura síncrona exit0, cerrada por helper; ningún lanzamiento de apps.
Fuente262: sólo provider y test dueño editados. Registro LLM intacto; Qwen3.5
sigue candidato por override. C03 íntegro EN_CURSO.
'''
(base/'CATALOGO_STEAM261_262.md').write_text(report,encoding='utf-8')
files = [base/'CATALOGO_STEAM261_262.md',root/'scratchpad/c03-retrieval261.py',
    root/'scratchpad/c03-startapps261.ps1',root/'scratchpad/c03-core262.py',
    root/'scratchpad/c03-finish262.py',
    root/'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs',
    root/'tests/Baxy.Providers.Windows.Tests/WindowsInstalledApplicationOpenProviderTests.cs']
files += sorted(p for p in out.rglob('*') if p.is_file())
files += [base/'astra-retrieval261'/name for name in ['PREREG.json','RESULT.json']]
private_files = [private/'C03-retrieval261-private'/name for name in
    ['HELLO_CATALOGS.json','START_APPS_STEAM.json']]
private_files += [private/'C03-app-catalog262-private/HELLO_CATALOGS.json']
save(base/'TRAMO261_262_PINS.json',{'public':[{'path':str(p.relative_to(root)), 'sha256':sha(p)} for p in files],
    'private':[{'privatePath':str(p),'sha256':sha(p)} for p in private_files]})
state = '''# C03 — checkpoint262 — EN_CURSO

Goal íntegro activo, Goal-c03, main preservada. Último cambio262: provider de
aplicaciones descarta alias duplicado con destino .exe local comprobado ausente
sólo cuando hay una identidad existente y ninguna alternativa desconocida.
No excepción Steam ni cambios en accesos directos. CATALOGO_STEAM261_262.md,
TRAMO261_262_PINS.json; antes en astra-app-catalog262/before.

Pruebas dueñas39pass/0skips108ms; Fast verde Release22,27s0warnings/errors.
Nuevo hello Core:292→293 aplicaciones, sólo añade Steam;169 operaciones iguales.
Fuente Python257 intacta; última validación171pass/0skips. No Full durante reparación.

UI260 anterior (PRUEBAS_UI260.md) midió3516,66MiB VRAM/4822,60MiB RAM600,51s:
UI/LLM/captura/AEC/Piper juntos.8800frames observados,9hablas mientras escucha,
sin ASR humano ni wake certificado. Volumen restaurado; procesos cerrados.
Usuario confirmó mensajes por texto: desarrollo humano, no reserva.

No confundir identidad reparada con tarea resuelta: primera petición «Tengo en
mente que abras steam» dejó app.open fuera de shortlist28 (rango116), eligió
game.launch y veto→unsupported. «abre steam» ya resuelve identidad tras262;
frase larga y «Si, abre steam» siguen null en helper aislado. UI260 también negó
falsamente capacidades generales tras fallo. No parchear prosa sin trazar causa.

Siguiente263: arrancar py main.py con fuente262 y mismo Qwen3.5, capturar payloads
reales de selector además de voz; comprobar «abre steam» y los dos seguimientos
literales260. Comparar cada transformación con catálogo actualizado, conservando
historial. No reutilizar260como reserva. Si falta app.open en retrieval, medir
alternativa antes de modificar. Modelo sigue override, registro intacto.

Ningún proceso propio activo.72258,63898,98309,26242 exit0 recogidos. No reiniciar.
Pendiente entero: ocho rutas,100/100humanos frescos (742 únicos/239 revisados;
ingleses históricos ya admitidos), averías/recuperación, recursos con ASR real,
perfil/registro/instalación, continuidad C04–C09, Full final y publicación fuera main.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    (base/name).write_text(state,encoding='utf-8')
relay = read(base/'RELEVO_ACTIVO.json')
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='262: identidad Steam recuperada en hello,39tests/0skips y Fast verde. Sin procesos.',
    continuation='263 UI fuente262 y payloads selector; resolver retrieval y capacidades falsas antes de reserva/promoción.')
save(base/'RELEVO_ACTIVO.json',relay)
print(json.dumps({'publicPins':len(files),'privatePins':len(private_files),'checkpoint':262}))
