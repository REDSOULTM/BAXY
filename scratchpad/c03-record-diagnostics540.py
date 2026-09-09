"""Close native diagnostics with literal evidence and explicit rejection reasons."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY'
decisions={
 'catalog-semantics537':('No adoptado. Las descripciones canónicas no reparan el guardado ni la capacidad. El resultado de capacidad añade el límite no demostrado «Solo tengo acceso a la información que se me proporciona en cada interacción».',
   'El watchdog heredado lanzó TypeError al comparar la primera lectura GPU None con3800. El proceso terminó y fue cerrado, y el muestreador registró3497,56MiB; esta corrida NO acredita vigilancia activa ni cumplimiento continuo del límite. Se corrigió la espera acotada de telemetría en538–540, sin alterar537 ni repetirlo.'),
 'relevant-result538':('No adoptado. El contrato general más claro mantiene metanarración al guardar y añade «no sensitive data was processed», que el indicador de ruta sensitive:false no demuestra. La respuesta de capacidad distingue estado inactivo, pero no compensa el defecto del guardado.',
   '22 respuestas EOS. Modelo, configuración registrada y hechos originales sin cambios; vigilancia con adquisición acotada de telemetría.'),
 'mutation-target539':('No adoptado. Recuperar el selector verificado que descarta la proyección mejora el tema de tres variantes, pero las cuatro siguen recitando indicadores. El caso name agrega que no hubo contenido sensible sin demostrarlo. El hallazgo de pérdida del selector no basta para cambiar la proyección.',
   '8 respuestas EOS. Una captura original y tres recibos contrafactuales de desarrollo; no se afirma haber guardado esos tres registros. Valores de memoria nunca añadidos.'),
 'configuration-contract540':('No adoptado. Aislar sólo la distinción entre configuración y existencia conserva la precisión de estado inactivo, pero sigue agregando «no sensitive data was detected» al guardar y más lenguaje interno al habilitar. No se incorpora una instrucción global con esas regresiones.',
   '22 respuestas EOS. Se aisló una cláusula medida de538; ninguna modificación del producto ni promoción de runtime.'),
}
for name,(decision,limitation) in decisions.items():
    out=base/('astra-'+name)
    captures=private/('C03-'+name+'-private')
    with (captures/'requests.jsonl').open(encoding='utf-8') as handle:
        requests=list(map(json.loads,handle))
    with (captures/'responses.jsonl').open(encoding='utf-8') as handle:
        responses=list(map(json.loads,handle))
    assert len(requests)==len(responses)
    resources=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8'))
    rows=[f'# C03 — {name}', '', decision, '', limitation, '',
          'Son diagnósticos nativos locales, no producto completo, UI, voz ni cobertura individual de la encuesta. No cambia la fuente120713be. Encuesta:0cubiertos/742abiertos/0no aplicables.', '',
          f'Recursos del servidor: GPU{resources["gpu_peak_mib"]:.3f}MiB, RAM{resources["ram_peak_mib"]:.3f}MiB, {resources["seconds"]}s. No es el consumo conjunto de BAXY.', '',
          '## Entradas y salidas literales','']
    for request,response in zip(requests,responses,strict=True):
        assert request['case']==response['case'] and request['profile']==response['profile']
        choice=response.get('response',{}).get('choices',[{}])[0]
        rows.extend([f'### {request["case"]} — {request["profile"]}', '',
                     'Entrada nativa:', '', '```text',
                     request['payload']['messages'][1]['content'], '```', '',
                     'Respuesta:', '', choice.get('message',{}).get('content','[sin respuesta]'), '',
                     f'Fin: {choice.get("finish_reason","error")}; latencia{response["seconds"]:.3f}s.', ''])
    (out/'RESULT.md').write_text('\n'.join(rows),encoding='utf-8')
    result={'utc':datetime.now(timezone.utc).isoformat(),'decision':'rejected_no_source_adoption',
            'reason':decision,'limitation':limitation,'response_count':len(responses),
            'eos_count':sum(r.get('response',{}).get('choices',[{}])[0].get('finish_reason')=='stop' for r in responses),
            'survey':{'covered':0,'open':742,'not_applicable':0}}
    (out/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='PINS.json'}
    (out/'PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
print('537–540 closed: four rejected candidates; no product source changes.')
