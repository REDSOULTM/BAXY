"""Manual adjudication and literal export of pilot1; no regenerated answers."""
from pathlib import Path
import hashlib
import json
import re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/comprobaciones/C03'
FOLDER=BASE/'astra-lora-pilot-evaluation';SOURCE=FOLDER/'replies.jsonl'
rows=[json.loads(line) for line in SOURCE.read_text(encoding='utf-8').splitlines()]
assert len(rows)==42
passed={
 'base':{'day-night-en','heat-metal-es','heat-metal-en','audio-holdout-0-en','audio-holdout-1-en','previous-t13','previous-t14'},
 'pilot_lora':{'day-night-es','day-night-en','day-night-mixed','heat-metal-es','audio-holdout-0-es','audio-holdout-0-en',
               'audio-holdout-0-mixed','audio-holdout-1-es','audio-holdout-1-en','previous-t13','previous-t14','previous-t4'},
}
notes={
 ('base','day-night-es'):'Confunde alejarse del Sol con quedar orientado al lado opuesto; «unos 24 horas» es incorrecto.',
 ('base','day-night-mixed'):'Sólo español; inventa un ciclo fijo de 12 horas y que sin rotación todo sería luz.',
 ('base','heat-metal-mixed'):'Sólo español, con «del sopa» y cierre innecesario; no satisface idioma/naturalidad.',
 ('base','audio-holdout-0-es'):'Omite si está silenciado y la unidad del volumen.',
 ('base','audio-holdout-1-es'):'Omite que el audio está silenciado.',
 ('base','audio-holdout-0-mixed'):'Hechos correctos, pero sólo español.',
 ('base','audio-holdout-1-mixed'):'Hechos correctos, pero sólo español.',
 ('base','previous-t8'):'Una palabra inglesa aislada no cumple la combinación natural de frases ES/EN.',
 ('base','previous-t9'):'Backup como préstamo aislado no satisface el spanglish solicitado.',
 ('base','previous-t10'):'Analogía de pegarse imprecisa y mezcla limitada al nombre inglés.',
 ('base','previous-t15'):'Definición inicial circular y sólo español pese a pedir spanglish.',
 ('base','previous-t2'):'Introduce la palabra inexistente «desmudado».',
 ('base','previous-t4'):'Datos correctos, pero redacción técnica innecesaria («mute state is off») en vez de narración natural.',
 ('base','previous-t6'):'Sólo español; no satisface spanglish.',
 ('pilot_lora','heat-metal-en'):'Explicación tautológica y poco natural: la cuchara transfiere calor desde la sopa a la cuchara, sin explicar la conducción.',
 ('pilot_lora','heat-metal-mixed'):'Mezcla forzada «El metal spoon» y «contacto directo con el calentamiento»; no logra naturalidad.',
 ('pilot_lora','audio-holdout-1-mixed'):'Conserva los hechos, pero sólo español.',
 ('pilot_lora','previous-t8'):'Sólo español y sustituye cifrado por el concepto más amplio de criptografía.',
 ('pilot_lora','previous-t9'):'Repite una traducción completa, expresamente excluida por el contrato de spanglish.',
 ('pilot_lora','previous-t10'):'La explicación mejora, pero responde sólo en inglés.',
 ('pilot_lora','previous-t15'):'Sólo español; además reduce archivo a documento, aunque puede contener otros datos.',
 ('pilot_lora','previous-t2'):'Afirma audio desactivado cuando muted=false: inversión de un hecho verificado.',
 ('pilot_lora','previous-t6'):'Hechos conservados, pero sólo español.',
}
def literal(text):
    fence='`'*max(3,max((len(x)+1 for x in re.findall(r'`+',text)),default=3))
    return f'{fence}text\n{text}\n{fence}\n'
body=['# C03 — piloto de ajuste: preguntas y respuestas literales\n',
      '**42 respuestas directas: 21 casos repetidos con base y adaptador. No son aceptación ni nuevas lecturas del PC.**\n',
      'Revisión individual del asistente: base 7/21 útiles, fieles y adecuados al idioma; piloto 12/21. '
      'En los 12 casos reservados del piloto: 5/12 frente a 9/12. Hay mejora parcial, pero el adaptador '
      'invierte el silencio al combinar hora/audio y sigue fallando en idioma con historial. **No promovido.**\n',
      'La pérdida de entrenamiento y el uso de memoria no cuentan como aciertos. Los objetivos de entrenamiento '
      'fueron escritos por el asistente; las respuestas siguientes sí proceden del modelo local.\n',
      ' · '.join(f'[{name}](<{(FOLDER/name).as_posix()}>)' for name in ['PREREG.json','RESULT.json','replies.jsonl'])+'\n']
adj=['# Adjudicación individual — primer piloto\n','Diagnóstico directo, no aceptación. Adjudicación manual posterior a la captura.\n',
     '| Variante | Caso | Resultado | Motivo |\n|---|---|---|---|']
checks=[]
for row in rows:
    variant,identifier=row['variant'],row['id'];ok=identifier in passed[variant]
    note=notes.get((variant,identifier),'Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado.')
    assert ok or (variant,identifier) in notes
    verdict='APROBADO' if ok else 'NO APROBADO'
    answer=row['response']['choices'][0]['message']['content']
    body += [f'## {variant} · {identifier}\n','**Entrada literal**\n',literal(row['request']),
             '**Respuesta literal**\n',literal(answer),f'**{verdict}:** {note}\n']
    adj.append(f'| {variant} | {identifier} | {verdict} | {note} |')
    checks += [literal(row['request']),literal(answer)]
text='\n'.join(body)+'\n';assert all(value in text for value in checks)
report=BASE/'PRUEBAS_AJUSTE_C03.md';report.write_text(text,encoding='utf-8')
(FOLDER/'ADJUDICACION.md').write_text('\n'.join(adj)+'\n',encoding='utf-8')
manifest={'responses':42,'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest(),
          'passed':{variant:sorted(ids) for variant,ids in passed.items()},'verbatimChecked':True}
report.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report':str(report),'responses':42,'verbatimChecked':True},ensure_ascii=False))
