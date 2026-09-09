from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
folders=['astra-boundary-product-qwen','astra-clarification-continuation-qwen',
         'astra-product-default-kv-qwen','astra-clarification-repaired-qwen',
         'astra-clarification-grounded-qwen','astra-clarification-unified-qwen']
report=['# C03: límites de capacidad y continuación de aclaraciones',
        'Pruebas de desarrollo, no aceptación fresca. Se conserva cada turno y cada intento fallido. '
        'El modelo GGUF sigue bajo override durante estas capturas; el manifiesto registrado permanece intacto. '
        'El conductor verifica publicación y estado, no inspección gráfica ni reproducción acústica.',
        'La ruta de identidad no disponible en el catálogo ahora utiliza el compositor de errores existente. '
        'La primera prueba de continuidad descubrió dos causas: una clave anidada se interpretaba como palabra '
        'cortada y se perdía la condición de efecto verificado; la App convertía una aclaración rechazada '
        'en conversación sin conservar su objetivo. Las correcciones y las pruebas automáticas están en ASTRA-TRAMO-28.md.']
for name in folders:
    folder=base/name
    if not (folder/'paired.json').exists():
        continue
    rows=json.loads((folder/'paired.json').read_text(encoding='utf-8-sig'))
    result=json.loads((folder/'RESULT.json').read_text(encoding='utf-8-sig'))
    parts=[f'# {name}', 'Entradas y respuestas literales del conductor. Las expectativas se adjudican por contenido y estado; publicación no equivale a aprobación.']
    verdicts={}
    for row in rows:
        ident=row['turnId']; verdict='ÚTIL'; reason='Responde al turno; revisar los hechos y límites de la captura enlazada.'
        if row['terminal']!='published_final':
            verdict='FALLO'; reason='No hubo respuesta final publicada.'
        elif name=='astra-boundary-product-qwen' and ident=='t7':
            verdict='FALLO DE CONTINUIDAD'; reason='La pregunta se publicó como conversación sin conservar aclaración pendiente; confirmado en la siguiente corrida de continuación.'
        elif name=='astra-clarification-continuation-qwen' and ident in {'t8','t9'}:
            verdict='FALLO'; reason='Aclaración sin estado pendiente (t8) y negativa falsa a la mezcla lingüística (t9); el 40% solicitado no se aplicó.'
        elif name=='astra-product-default-kv-qwen' and ident in {'t2','t5'}:
            verdict='FALLO'; reason='Audio desactivado contradice muted:false (t2); reunión y falta de tiempo inventadas (t5).'
        elif name=='astra-clarification-repaired-qwen' and ident in {'t8','t9'}:
            verdict='FALLO'; reason='Se conserva el objetivo pendiente, pero el dominio rechaza la coma tras volume; la continuación pregunta por descuento/tiempo y no aplica40%.'
        elif name=='astra-clarification-grounded-qwen' and ident=='t8':
            verdict='FALLO DE CONTINUIDAD'; reason='La decisión pasó por plan; esa ruta aún perdía la aclaración al rechazar su redacción. Se unificó después el manejo de decisión/plan/argumentos.'
        elif name=='astra-clarification-unified-qwen':
            reason='Revisión individual: responde y conserva estado; los niveles80/60/40 y restauración100 están comprobados en efectos y lecturas posteriores.'
            if ident=='t8':
                reason='Pregunta amplia sobre el audio que se quiere ajustar; conserva aclaración pendiente y la respuesta40% se aplica correctamente. Puede ser más directa al pedir el nivel.'
        verdicts[ident]={'verdict':verdict,'reason':reason}
        parts += [f'## {ident} — {verdict}', '**Entrada literal**\n```text\n'+row['request']+'\n```']
        if row['terminal']=='published_final':
            parts += ['**Respuesta literal**\n```text\n'+row['final']+'\n```']
        else:
            parts += ['**Sin respuesta final.** Marcador interno del conductor: '+str(row['final'])+'.']
        parts += [reason, 'Terminal: '+row['terminal']+'.']
    (folder/'RESPUESTAS.md').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
    (folder/'ADJUDICACION.json').write_text(json.dumps(verdicts,ensure_ascii=False,indent=2),encoding='utf-8')
    if name=='astra-clarification-unified-qwen':
        for ident,level in [('t3',80),('t6',60),('t9',40),('t11',100)]:
            row=next(r for r in rows if r['turnId']==ident)
            situations=[json.loads(c['situation']) for c in row['compose'] if c.get('situation')]
            assert any(s.get('verified') is True and s.get('succeeded') is True
                       and s.get('observed',{}).get('applied') is True
                       and s.get('observed',{}).get('final',{}).get('volumePercent')==level
                       for s in situations),(ident,level)
    files=['RESPUESTAS.md','ADJUDICACION.json','paired.json','PREREG.json','RESULT.json']
    (folder/'REPORT_MANIFEST.json').write_text(json.dumps({'acceptance':False,'files':{
        p:hashlib.sha256((folder/p).read_bytes()).hexdigest() for p in files}},indent=2),encoding='utf-8')
    report += [f'## {name}',f"{len(rows)} turnos, {sum(r['terminal']=='published_final' for r in rows)} publicados; {result['elapsedSeconds']} s; pico GPU {result['gpuPeakMiB']:.2f} MiB.",
               f"[Todos los turnos](<{(folder/'RESPUESTAS.md').as_posix()}>) · [Prompts y respuestas de todos los roles](<{(folder/'sampling.jsonl').as_posix()}>) · [Condiciones previas](<{(folder/'PREREG.json').as_posix()}>)"]
dest=base/'PRUEBAS_CONTINUIDAD_C03.md'
dest.write_text('\n\n'.join(report)+'\n',encoding='utf-8')
print(dest)
