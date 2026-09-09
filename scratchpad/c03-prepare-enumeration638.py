"""Pin complete window enumeration before the second product measurement."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03';out=base/'astra-enumeration-source638'
out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
paths=['src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs','tests/Baxy.Providers.Windows.Tests/WindowsInstalledApplicationOpenProviderTests.cs','tests/Baxy.Providers.Windows.Tests/InstalledApplicationWindowEnumerationTests.cs']
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source':638,
    'sources':{p:sha(root/p) for p in paths},'python_unchanged':True,
    'method':'Second difference after637: retain all visible top-level HWNDs with positive area, largest-first for launch selection; focus the exact selected handle instead of silently substituting the largest. Keep636 authenticated package identity and honest identity/enumeration errors.',
    'test_first':'Real Win32 fixture with two visible HWNDs and one hidden HWND fails before change (one missing), then51targeted pass including it. Test windows offscreen, never activated, owned handles destroyed in finally. No user window touched.',
    'owners':{'passed':513,'aggregate_skipped':0,'printed_opt_in_omissions':4,'seconds':46},
    'criteria':'Fast green; product639 same12panel634/637 plus independent native HWND snapshots before/after. Compare actual cardinality and exact observations. Preserve app scope, names, language; record known focus-en language failure separately. No UI/voice credit or survey coverage without per-case adjudication.'})
for original,target in [('c03-enumeration638-red-native.log','RED_NATIVE.log'),('c03-enumeration638-targeted.log','TARGETED.log'),('c03-enumeration638-providers.log','PROVIDERS.log')]:
    (out/target).write_bytes((Path(os.environ['TEMP'])/original).read_bytes())
(out/'source638.patch').write_bytes(subprocess.check_output(['git','diff','--binary','--',*paths],cwd=root))
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='637 confirma presencia Notepad;638 enumera todos los handles y conserva foco exacto. Test Win32 rojo previo→51pass;513dueñas/4opt-in impresas. Fast/producto639 pendientes.25/717/0.',continuation='Completar Fast638 y producto639 con instantáneas Win32 antes/después. Comparar cantidades y adjudicarH0040. Focus-en: token compartido has cuenta como evidencia exclusivamenteES; reparar después con controles Spanish/mixed/contexto.')
write(base/'RELEVO_ACTIVO.json',state)
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as f:f.write('\n\n## Candidato638 — todos los handles observados\n\nLa prueba Win32 falla antes: sólo una de dos ventanas visibles. Después51focales y513dueñas Providers verdes;4opt-in impresas aparte. Se conserva identidad636 y se retira la sustitución silenciosa del handle en foco. Fast y producto639 pendientes.637 detecta Notepad pero conserva conteo incompleto; no se fusionan las dos diferencias sin evidencia.25/717/0.\n')
print({'source':638,'providers_passed':513})
