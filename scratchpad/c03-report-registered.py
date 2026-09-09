"""Publish literal evidence with individual judgements made after reading it."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/comprobaciones/C03'
notes=[
'Hora16:17 equivalente al reloj observado; unidades horas/minutos conservadas.',
'FALLO DE NATURALIDAD: conserva16:17,volumen100 y desactivación de muteo, pero inventa/desforma el término desmudo. No aprobado como prosa natural.',
'Hora16:17 correcta, inglés.',
'Hora16:17,volumen100,muted:false conservados en inglés.',
'Hora16:17 correcta; español válido para petición mixta.',
'Hora16:17,audio activo y nivel100 conservados.',
'Saludo natural; bienvenida y pregunta social admitidas por el dueño.',
'Explicación sencilla del cifrado con clave y analogía de candado; útil bajo la rúbrica del dueño.',
'Copia en otro lugar para recuperar datos perdidos o dañados; definición simple suficiente.',
'Explicación cotidiana de atracción hacia la Tierra; hilo presentado como analogía, no hecho literal.',
'Respeta no abrir Paint; no anuncia ejecución.',
'Lima es la capital de Perú.',
'Dos oraciones; fotosíntesis explica luz,agua,CO2,glucosa y oxígeno.',
'Menor densidad del hielo por expansión: explicación correcta.',
'Ejemplos distinguen archivo de contenedor; definición circular inicial mejorable, pero diferencia útil.',
'Lista vacía en el perfil de prueba según lectura real; no extrapolar al resto de perfiles.',
'Pregunta por confirmar/cancelar el cierre de la ventana concreta, antes del efecto.',
'Cancela la solicitud, conserva que no se cerró la ventana.',
'Nueva pregunta de confirmación para la ventana concreta; no reutiliza autorización cancelada.',
'Cierre de fixture propio confirmado por producto y por su proceso terminado antes de limpieza.',
'Hora16:17 en inglés; sesión continúa tras cierre.',
'Estado real inicial: volumen100,muted:false.',
'Pregunta por nivel/dirección faltantes y conserva objetivo pendiente.',
'Nivel80 aplicado,verified+succeeded+observed.applied verdaderos; sin muteo.',
'Lectura posterior80 coincide. Mutado es un préstamo/errata poco elegante; el nivel solicitado y la ausencia de muteo se entienden.',
'Pregunta en inglés por ajuste faltante y conserva objetivo.',
'Nivel60 realmente aplicado y narrado en inglés, sin muteo.',
'Lectura posterior60 con mute off coincide.',
'Pregunta concreta por nivel; comprende petición mixta y conserva objetivo.',
'Fragmento40% resuelve aclaración; efecto verificado y narración correcta.',
'Lectura posterior40 coincide.',
'Restauración real al100%,verificada y narrada.',
'Lectura final100,muted:false; estado original restaurado.',
]
report=['# C03 — runtime registrado, UI y recuperación',
'C03 EN_CURSO. Qwen3-4B-Instruct-2507 Q4_K_M registrado, KVq8 por defecto. No son100 turnos nuevos. La tanda integrada tiene33 respuestas normales publicadas:32 útiles y1 fallo de naturalidad. Las tres averías y los tres turnos restaurados se evalúan aparte. No se acredita progreso narrado: esta tanda no produjo una frase de progreso separada.',
'Ventana real observada con la skill de Windows tras `py main.py`, sin overrides de modelo/voz/Python. Se vio Qwen4b local, activación encendida, error de recuperación de memoria, cancelación manual y respuesta de hora/audio. Pico del árbol real con voz:3589,12MiB. No acredita por sí solo habla física/STT ni toda la ruta de hardware.',
f'[Detalle del tramo y limitaciones](<{(BASE/"ASTRA-TRAMO-29.md").as_posix()}>)']
for name in ['astra-registered-development-recovery-qwen','astra-registered-integrated-qwen']:
    folder=BASE/name;rows=json.loads((folder/'paired.json').read_text(encoding='utf-8'))
    integrated=name=='astra-registered-integrated-qwen';normal=33 if integrated else 21
    parts=[f'# {name}','Pruebas conocidas de desarrollo. Publicación y utilidad se evalúan por separado. Las inyecciones no cuentan como turnos normales.']
    verdicts={}
    for i,row in enumerate(rows):
        if i<normal:
            if integrated: reason=notes[i];ok=i!=1
            else:
                ok=i not in {0,4}
                reason=('Sin respuesta: borrador correcto con horas/minutos rechazado.' if i==0 else 'Sin respuesta: conversiones16:09→4:09 sin PM, reintento inventa un día de Ana.' if i==4 else notes[i] if i!=1 else 'Hora16:09,volumen100 y muteo desactivado conservados; redacción mejorable.')
                reason=reason.replace('16:17','16:10' if i==20 else '16:09')
            verdict='ÚTIL' if ok else 'FALLO'
        elif row['injection']!='none':
            errors=[e for e in row['publicEvents'] if e.get('type')=='composition_failed']
            assert errors and all(e.get('injected') and e.get('controlsUsable') for e in errors)
            verdict='AVERÍA INYECTADA — ESTADO RECUPERABLE'
            reason='Sin prosa por avería forzada. Estado composition_failed visible en protocolo, causa conservada y controles usables; no es una respuesta normal aprobada.'
        else:
            assert row['terminal']=='published_final' and not row['posterior']['hasCompositionError']
            verdict='RECUPERACIÓN ÚTIL'
            reason='Tras restore, responde la hora correcta en la misma sesión y retira el error; se conserva fuera de la muestra normal.'
        verdicts[row['turnId']]={'verdict':verdict,'reason':reason}
        parts += [f'## {row["turnId"]} — {verdict}', '**Entrada literal**\n```text\n'+row['request']+'\n```']
        if row['terminal']=='published_final':parts += ['**Respuesta literal**\n```text\n'+row['final']+'\n```']
        else:parts += ['**Sin respuesta final.** Estado de producto: `'+row['terminal']+'`.']
        parts += [reason]
    (folder/'RESPUESTAS.md').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
    (folder/'ADJUDICACION.json').write_text(json.dumps(verdicts,ensure_ascii=False,indent=2),encoding='utf-8')
    report += [f'## {name}',f'[Entradas, respuestas y veredictos individuales](<{(folder/"RESPUESTAS.md").as_posix()}>)',f'[Hechos y auditorías emparejados](<{(folder/"paired.json").as_posix()}>)']
direct=BASE/'astra-registered-compose-choice-question'
rows=[json.loads(s) for s in (direct/'replies.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(rows)==9 and all(r['answer'] and not r['error'] for r in rows)
report += ['## Nueve regresiones directas del compositor','Hechos sintéticos exactos, no efectos nuevos sobre el PC.9/9 útiles:3horas,3recuperaciones de memoria y3de audio. Las opciones retry se conservan como token que ofrece el shell; las respuestas españolas pueden mejorar estilo. El diagnóstico inicial omitió requiredResponseWords y tiene ERRATA explícita; no se presenta como medición fiel del shell.']
for r in rows:report += [f'### {r["id"]}','```text\n'+r['request']+'\n```','```text\n'+r['answer']+'\n```']
dest=BASE/'PRUEBAS_RUNTIME_REGISTRADO_C03.md';dest.write_text('\n\n'.join(report)+'\n',encoding='utf-8')
sources=[BASE/'astra-registered-integrated-qwen/paired.json',BASE/'astra-registered-development-recovery-qwen/paired.json',direct/'replies.jsonl',dest]
dest.with_suffix('.manifest.json').write_text(json.dumps({'freshAcceptance':False,'individualReview':True,'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},indent=2),encoding='utf-8')
print(dest)
