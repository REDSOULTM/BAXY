"""Manual, per-answer evaluation of the format coverage pilot, preserving raw text."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/comprobaciones/C03'
folder=BASE/'astra-lora-pilot3-evaluation';source=folder/'replies.jsonl'
rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines()]
assert len(rows)==78
previous={}
for line in (BASE/'astra-lora-pilot2-evaluation/ADJUDICACION.md').read_text(encoding='utf-8').splitlines():
    cells=[x.strip() for x in line.split('|')]
    if len(cells)==6 and cells[1]=='pilot_lora':previous[cells[2]]=(cells[3]=='APROBADO',cells[4])
assert len(previous)==27
new2fail={
 'format-heldout-perimeter-es':'Una sola oración; se pidieron dos.',
 'format-heldout-perimeter-mixed':'Sólo español.',
 'format-heldout-pendulum-es':'Una sola oración; se pidieron dos.',
 'format-heldout-pendulum-mixed':'Una sola oración y traducción repetida de la misma explicación.',
 'format-heldout-spacing-es':'Una sola oración; se pidieron dos.',
 'format-heldout-spacing-mixed':'Una sola oración; se pidieron dos.',
 'format-heldout-calendar-es':'Una sola oración; se pidieron dos.',
 'format-heldout-calendar-mixed':'Una sola oración con punto y coma y sólo español.',
}
new3fail={
 'heat-metal-mixed':'Vuelve a cambiar la cuchara de la pregunta por un cuchillo.',
 'previous-t8':'La segunda oración niega que el cifrado haga ilegibles los datos; contradice la explicación de protección mediante clave.',
 'previous-t14':'Dice que ocupa más espacio que el mismo volumen: comparación contradictoria. Debía comparar una misma cantidad o masa.',
 'previous-t15':'Responde sólo en español a la petición explícita de Spanglish.',
 'format-heldout-perimeter-mixed':'«A un cuadrado con lados de 5 cm» queda mal construido; no es una respuesta natural.',
 'format-heldout-pendulum-es':'Invoca inercia y transformación en calor sin explicar fricción o resistencia; no explica correctamente por qué se frena.',
 'format-heldout-spacing-mixed':'La oración inglesa vuelve a expresar completa la misma explicación española.',
}
body=['# C03 — tercer ajuste: comparación literal de formato y calidad\n',
      '**78 respuestas: 39 con v2 y 39 con v3. Desarrollo, no aceptación.**\n',
      'Revisión manual: v2 25/39 y v3 32/39. En los 12 casos nuevos de formato: 4/12 frente a 9/12. '
      'En los 27 casos previos: 21/27 frente a 23/27. **V3 no se promueve:** mejora el formato, '
      'pero regresa en la explicación del hielo y mantiene errores importantes en cifrado. '
      'Un aumento del total no compensa publicar hechos falsos.\n',
      'Se reutilizan peticiones y hechos congelados; las respuestas provienen del modelo local y se conservan sin corregir. '
      'Las 27 respuestas de control v2 son idénticas a las de su evaluación anterior. '
      'Los hechos sintéticos no son lecturas nuevas del PC.\n',
      ' · '.join(f'[{n}](<{(folder/n).as_posix()}>)' for n in ['PREREG.json','RESULT.json','replies.jsonl'])+'\n']
adj=['# Adjudicación individual — formato v2 frente a v3\n',
     '| Variante | Caso | Resultado | Motivo |\n|---|---|---|---|']
counts={'pilot2':0,'pilot3':0};newcounts={'pilot2':0,'pilot3':0}
for r in rows:
    variant,identifier=r['variant'],r['id']
    if variant=='pilot2' and identifier in previous:ok,note=previous[identifier]
    else:
        fails=new2fail if variant=='pilot2' else new3fail
        ok=identifier not in fails;note=fails.get(identifier,'Respuesta útil y fiel, con idioma y formato solicitados.')
        if variant=='pilot3' and identifier=='previous-t2':note='Hora, volumen y silencio correctos. Desmutado se entiende aquí como estado no silenciado; no se exige una frase exacta.'
    counts[variant]+=ok
    if identifier.startswith('format-heldout'):newcounts[variant]+=ok
    verdict='APROBADO' if ok else 'NO APROBADO';answer=r['response']['choices'][0]['message']['content']
    body.extend([f'## {variant} · {identifier}\n',f"**Entrada literal**\n\n```text\n{r['request']}\n```\n",
                 f'**Respuesta literal**\n\n```text\n{answer}\n```\n',f'**{verdict}:** {note}\n'])
    adj.append(f'| {variant} | {identifier} | {verdict} | {note} |')
assert counts=={'pilot2':25,'pilot3':32},counts
assert newcounts=={'pilot2':4,'pilot3':9},newcounts
text='\n'.join(body)+'\n';report=BASE/'PRUEBAS_AJUSTE_3_C03.md';report.write_text(text,encoding='utf-8')
for r in rows:assert '\n'+r['request']+'\n' in text and '\n'+r['response']['choices'][0]['message']['content']+'\n' in text
(folder/'ADJUDICACION.md').write_text('\n'.join(adj)+'\n',encoding='utf-8')
report.with_suffix('.manifest.json').write_text(json.dumps({'responses':78,'passed':counts,'formatHoldoutPassed':newcounts,
 'verbatimChecked':True,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print(json.dumps({'responses':78,'passed':counts,'formatHoldoutPassed':newcounts,'verbatimChecked':True}))
