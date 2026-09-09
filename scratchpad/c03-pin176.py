"""Finish176, pin new evidence, and leave a current bounded handoff."""
from pathlib import Path
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
import subprocess

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-linear176'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
original=Path('D:/BAXYRuntime/experiments/voice/webrtc174/source/pywebrtc_audio-0.2.0/bindings/webrtc_audio_bindings.cpp')
diagnostic=Path('D:/BAXYRuntime/experiments/voice/webrtc176/source/bindings/webrtc_audio_bindings.cpp')
(out/'diagnostic.patch').write_text(''.join(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True),diagnostic.read_text(encoding='utf-8').splitlines(True),fromfile='upstream/bindings/webrtc_audio_bindings.cpp',tofile='diagnostic/bindings/webrtc_audio_bindings.cpp')),encoding='utf-8')
for name in ['c03-linear176-build.log','c03-linear176-evaluate.log']:
    (out/name).write_bytes((Path(os.environ['TEMP'])/name).read_bytes())
rows=json.loads((out/'RESULTS.json').read_text(encoding='utf-8'))
assert len(rows)==6 and all(r['finalPcmIdenticalTo174'] for r in rows)
branch=subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()
assert branch=='Goal-c03'
snapshot=json.loads((base/'astra-source172-snapshot/INDEX.json').read_text(encoding='utf-8'))
assert all(sha(root/r['copy'])==r['sha256'] for r in snapshot)
assert sha(root/'src/baxy_mind/voice.py')==next(r['sha256'] for r in snapshot if r['source'].endswith('voice.py'))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
report='''# C03 — pérdida entre salida lineal y supresión residual —176

La salida final de la compilación diagnóstica coincide bit a bit (PCM16) con
la wheel174 en los tres controles. La observación no cambió esa salida.
Build9568 exit0; evaluación83450 exit0. Visual Studio17 2022, x64, Release;
wheel316.966bytes SHA718f8681940df85abb3535790721b3fc735a564a0e7fbb82f5ed747401816e69.
No se instala en el runtime ni se modifica código de producto.

## Qué se observó

La API existente EchoControl::ProcessCapture permite exportar la salida lineal.
Se activa sólo export_linear_aec_output y se lee esa señal junto a GetMetrics.
No se cambian delay, filtros, supresión, detector de BAXY ni señales de entrada.
El diff reproducible está en astra-linear176/diagnostic.patch; fuente upstream
descargada174 y compilación176 permanecen fuera del repositorio por ruta/hash.

| Control | Etapa | Bloques de habla | Mayor secuencia sin guard | Parakeet crudo | Normalizado |
|---|---|---:|---:|---|---|
'''
for r in rows:
    words=[t['text'] or '(vacío)' for t in r['transcripts']]
    report+=f"| {r['case']} | {r['stage']} | {r['speechFrames']} | {r['longestQualifiedWithoutGuard']} | {words[0] if words else 'no ejecutado'} | {words[1] if words else 'no ejecutado'} |\n"
report+='''
En mezcla, la salida lineal conserva «¿En qué te puedo ayudar?» y la residual
produce «Exactly.» ante Parakeet. La primera tampoco recupera saludo/nombre/hoy.
Esto localiza pérdida adicional entre etapas; no prueba que cada palabra ausente
se deba a la misma causa ni autoriza alimentar STT con una señal aún incompleta.
La salida lineal del eco149 conserva119bloques de habla frente a0residuales:
quitar la supresión dejaría nuevamente eco. No adoptar ese atajo.

Los ASR176 reciben floats nativos antes de exportar WAV;174/175 leen PCM16.
Variantes de nombre en el control cercano no se atribuyen a diferencias del
cancelador porque la salida PCM16 es idéntica. Todos los resultados se conservan.

## Métricas y límite causal

En la mezcla127/129 la demora estimada pasa de0ms a48ms entre25,5 y26s;
ERLE reportado permanece~0,176dB hasta27,5s y crece después. Eso describe
convergencia tardía; no prueba por sí solo la causa de la pérdida de palabras.
La alineación127/129 viene de streamReadyUtc y es aproximada.149 sí usa los
arrays nativos exactos pero no contiene voz cercana independiente.

Lectura de aec_state.cc93–100/283–312 descarta cambiar a ciegas
conservative_initial_phase: prolonga adaptación (no una reparación demostrada).
echo_remover.cc selecciona Y/E según UseLinearFilterOutput y calcula G con
nearend_spectrum/echo_spectrum/R2 antes de ApplyGain. Configuración de supresión
no se toca hasta contrastar esos estados y la relación temporal del control.

## Continuación concreta

Analizar la referencia y la voz cercana129 con sus tiempos reales de señal,
comparar comienzo de far-end con near_start y demora/ERLE176. No usar speaking
como comienzo acústico: OutputStream ya mostró latencia al abrir. Determinar
si el fallo es anterior a una estimación útil y contrastar protección de doble
habla con fuente upstream. Reutilizar build176 (no recomprar contexto ni paquetes).
No repetir UI/otra corrida de voces sólo para buscar un pase.174/175/176 son
experimentos de componente, no aceptación de doble habla ni del producto.

Fuente172/manifest intactos; ningún proceso propio pendiente. No Full.
C03 EN_CURSO y todos sus criterios finales siguen íntegros.
'''
(base/'PRUEBAS_AEC176.md').write_text(report,encoding='utf-8')
public=[]
groups={
    'astra-sidecar173':['PREREG.json','RUNTIME_CONFIG.json','RESULTS.json','CLEANUP.json','INDEX.json','AUDIO_SETUP.json','AUDIO_READY.json','AUDIO_RESULT.json'],
    'astra-webrtc174':['PREREG.json','DOWNLOADS.json','INPUT_INDEX.json','RESULTS.json','COMPLETE.json','ASR_INDEX.json'],
    'astra-observe175':['PREREG.json','RESULT_INDEX.json'],
    'astra-linear176':['PREREG.json','RESULTS.json','BUILD.json','PRIVATE_INDEX.json','diagnostic.patch','c03-linear176-build.log','c03-linear176-evaluate.log'],
    'astra-source172-snapshot':['INDEX.json','voice.py','test_mind_voice_runtime.py','c03-source172-red.log','c03-source172-owner.log','c03-source172-fast.log']}
for folder,names in groups.items():
    public.extend(base/folder/name for name in names)
public.extend(base/n for n in ['ASTRA-TRAMO-172.md','PRUEBAS_AEC173_175.md','PRUEBAS_AEC176.md'])
public.extend(root/'scratchpad'/n for n in ['c03-prepare173.py','c03-capture173.py','c03-sidecar173.py','c03-sidecar173-entry.py','c03-prepare174.py','c03-evaluate174.py','c03-asr174.py','c03-observe175.py','c03-report175.py','c03-prepare176.py','c03-evaluate176.py'])
private=[]
for p in [base/'astra-sidecar173/INDEX.json',base/'astra-linear176/PRIVATE_INDEX.json',Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-webrtc174-private/INPUTS.json',Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-webrtc174-private/OUTPUT_INDEX.json']:
    for row in json.loads(p.read_text(encoding='utf-8')):
        assert sha(Path(row['privatePath']))==row['sha256']
        private.append(row)
audio=json.loads((base/'astra-sidecar173/AUDIO_RESULT.json').read_text(encoding='utf-8'))
assert audio['threadsStopped'] and audio['restoredExactly'] and all(s['overflows']==0 for s in audio['streams'].values())
for row in audio['streams'].values():
    assert sha(Path(row['privatePath']))==row['sha256']
    private.append({k:row[k] for k in ['privatePath','sha256']})
for name in ['ASR.json','OBSERVE175.json','INPUTS.json','OUTPUT_INDEX.json']:
    p=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-webrtc174-private'/name
    private.append({'privatePath':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
save(base/'TRAMO172_176_PINS.json',{'public':[{'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size} for p in public],'private':private})
note='''# Actualización176 — etapas de AEC3 verificadas; no adopción

Fuente172 sigue vigente; pruebas130/Fast verdes.173 físico2/4 cortes.
17415mediciones,17518observaciones y1766etapas completados exit0.
176 salida final bitidéntica a174; mezcla pierde más palabras en residual que
en lineal, que tampoco conserva todo y deja pasar eco149. No quitar supresión.
PRUEBAS_AEC173_175.md/PRUEBAS_AEC176.md y TRAMO172_176_PINS.json fijan evidencia.
Build9568/evaluación83450 terminados y recogidos; ningún proceso propio pendiente.
Siguiente: relación temporal real de far-end/near129 y convergencia176; no asumir
que speaking coincide con sonido. Reutilizar build176; no tunear sin causa.
No fuente/runtime/promoción/Full nuevos. C03 íntegro EN_CURSO.

'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name
    p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json';d=json.loads(p.read_text(encoding='utf-8'))
d.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='176 completo; paridadPCM3/3, pérdida adicional en residual; sin adopción. Fuente172/manifest intactos.',continuation='Analizar relación temporal real far/near129 frente a delay/ERLE176 y protección de doble habla; sin procesos activos. Preservar pins172–176 y resto C03 íntegro.')
save(p,d)
print(json.dumps({'publicPins':len(public),'privatePins':len(private),'branch':branch,'manifestIntact':True}))
