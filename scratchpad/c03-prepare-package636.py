"""Seal native identity635 and preregister the first provider repair636."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03';home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
out=base/'astra-package-identity635';result=json.loads((out/'RESULT.json').read_text(encoding='utf-8'))
assert not (out/'PINS.json').exists()
result['window_details_sha256']=sha(home/'C03-package-identity635-private/window-details-later.json')
result['count_limitation_confirmed']={'Notepad.exe':12,'steamwebhelper.exe':2}
write(out/'RESULT.json',result)
note='''# Auditoría635 — identidad y multiplicidad

GetApplicationUserModelId enlaza de forma exacta el proceso Notepad con Microsoft.WindowsNotepad_8wekyb3d8bbwe!App del catálogo.15procesos con ventanas visibles consultados, sin errores inesperados; ningún arranque, foco o cierre. El lector anterior no consulta esta identidad y los tokens del nombre localizado no coinciden.

La inspección de los handles también confirma otra limitación:12ventanas Notepad, todas visibles, no cloaked, sin owner y con área positiva;2ventanas de steamwebhelper, una pequeña88x15. Inventory conserva sólo la más grande de cada proceso. Los conteos634deben tratarse como incompletos; su10/12anterior valoraba plausibilidad del conteo y no acredita cardinalidad. H0040 sigue abierto. No se corrige multiplicidad junto con identidad sin medir la primera diferencia636/637.

Fuentes primarias consultadas2026-09-09: https://learn.microsoft.com/en-us/windows/win32/api/appmodel/nf-appmodel-getapplicationusermodelid y https://learn.microsoft.com/en-us/windows/configuration/store/find-aumid . GetApplicationUserModelId requiere QUERY_LIMITED_INFORMATION y distingue identidad ausente de error de consulta. La implementación anterior de WindowsApplicationPlatform.QueryPackageString aporta el patrón acotado de doble consulta y error honesto; no se reutiliza su política específica de Notepad como alias de aplicaciones generales. No salió contenido del usuario.
'''
(out/'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
out=base/'astra-package-source636';out.mkdir(exist_ok=False)
paths=['src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs','tests/Baxy.Providers.Windows.Tests/WindowsInstalledApplicationOpenProviderTests.cs']
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source':636,
    'sources':{p:sha(root/p) for p in paths},'python_unchanged':True,
    'method':'First difference: exact OS AUMID for packaged catalog entries. Native query error becomes inventory_failed, not verified absence or launch. Preserve classic identity and window selection for separate multiplicity measurement.',
    'owners':{'passed':512,'aggregate_skipped':0,'printed_opt_in_omissions':4,'seconds':55},
    'criteria':'Fast green then same12product634 in637. Notepad must be detected, Steam/Chrome/Spotify/Paint scope preserved. No write effects. Count remains known incomplete and cannot grant coverage. Focus English remains an independent known defect. No UI/voice/model/profile credit.'})
for original,target in [('c03-package636-owners.log','TARGETED.log'),('c03-package636-providers.log','PROVIDERS.log')]:
    (out/target).write_bytes((Path(os.environ['TEMP'])/original).read_bytes())
(out/'source636.patch').write_bytes(subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root))
with (root/'.gitattributes').open('a',encoding='utf-8',newline='\n') as f:f.write('/artifacts/comprobaciones/C03/astra-package-identity635/** -text\n')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as f:f.write('\n\n'+note+'\n636 candidato:512pass/0omisiones agregadas y4opt-in impresas;Fast/producto637 pendientes.25/717/0.\n')
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='635 confirma identidad OS y12ventanas Notepad/2Steam;636 candidatoC# pasa512dueñas. Fast/producto637 pendientes.25/717/0.',continuation='Completar Fast636 y repetir12panel634 en637 antes de cambiar multiplicidad. Después enumerar todas las ventanas conservando foco/identity/errores. No crédito de cardinalidad por634.',previousGoalTurnClassification='progress')
write(base/'RELEVO_ACTIVO.json',state)
print({'candidate':636,'native_audit':635,'owners_passed':512})
