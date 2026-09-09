"""Literal export and manual adjudication of the single adapter scale test."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/comprobaciones/C03'
folder=BASE/'astra-lora-pilot2-half-scale-ready';source=folder/'replies.jsonl'
rows=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines()]
fail={
 'day-night-mixed':'Repite la explicación completa en inglés después del español.',
 'heat-metal-mixed':'Traduce otra vez la misma explicación completa.',
 'audio-holdout-0-mixed':'Sólo español.',
 'audio-holdout-1-mixed':'Sólo español.',
 'compound-heldout-1-mixed':'Sólo español.',
 'previous-t8':'Sólo español.',
 'previous-t9':'La segunda parte vuelve a explicar lo mismo en inglés; traducción repetida.',
 'previous-t10':'Sólo inglés y error gramatical «a invisible».',
 'previous-t15':'Definición circular de archivo y sólo español; también omite que un archivo contenedor puede almacenar otros.',
 'previous-t2':'«Audio activo» no responde de forma inequívoca al estado de silencio; puede sugerir reproducción que no se observó.',
 'previous-t6':'Sólo español; muteado como préstamo no cumple mezcla natural de frases.',
}
assert len(rows)==27 and len(fail)==11
body=['# C03 — prueba de intensidad del adaptador\n',
 '**27 respuestas directas, 16 aprobadas y 11 no aprobadas. No son aceptación.** '
 'El adaptador v2 completo obtuvo 21/27 en estos mismos casos; la escala 0,5 pierde calidad de idioma. '
 'Se descarta esta escala. El runtime registrado no se modificó.\n',
 'La evaluación es manual. No se corrigió ninguna respuesta y no se cuentan los errores de arranque como respuestas.\n']
adj=['# Adjudicación — escala 0,5\n','| Caso | Resultado | Motivo |\n|---|---|---|']
for r in rows:
 answer=r['response']['choices'][0]['message']['content'];reason=fail.get(r['id'],'Respuesta útil, fiel y en el idioma solicitado.')
 verdict='NO APROBADO' if r['id'] in fail else 'APROBADO'
 body.extend([f"## {r['id']}\n",f"**Entrada literal**\n\n```text\n{r['request']}\n```\n",
              f'**Respuesta literal**\n\n```text\n{answer}\n```\n',f'**{verdict}:** {reason}\n'])
 adj.append(f"| {r['id']} | {verdict} | {reason} |")
text='\n'.join(body)+'\n';report=BASE/'PRUEBAS_ESCALA_C03.md';report.write_text(text,encoding='utf-8')
for r in rows:assert '\n'+r['request']+'\n' in text and '\n'+r['response']['choices'][0]['message']['content']+'\n' in text
(folder/'ADJUDICACION.md').write_text('\n'.join(adj)+'\n',encoding='utf-8')
report.with_suffix('.manifest.json').write_text(json.dumps({'responses':27,'passed':16,'verbatimChecked':True,
 'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print('Scale report: 27 literal responses, 16 pass, 11 fail.')
