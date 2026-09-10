"""Record manual review of all final answers, with exact evidence hashes."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03/K2_HORIZON_NATIVE699'
p=argparse.ArgumentParser()
p.add_argument('tag')
a=p.parse_args()
manual={
    '09-bf16-high-reference699':{
        'facts-01':'Responde24GiB usados en vez de15; confunde utilizable con usada.',
        'facts-04':'Inventa un archivo de grabación y confunde silencio con0dBFS.',
        'facts-05':'Añade hechos y procedimientos incorrectos de registro; afirma que reiniciar resetea permisos.',
        'facts-09':'Termina afirmando que un ping al router confirma Internet, contradiciendo su respuesta inicial.',
        'facts-14':'Asegura finalmente que el documento está incompleto pese a no haber verificación tras el timeout.',
        'facts-18':'Convierte la última lectura antigua en una lectura actual.',
        'facts-19':'Responde375GB libres cuando el dato explícito es125GB.',
        'knowledge-01':'Añade tiempos generales falsos: RAM milisegundos y almacenamiento segundos/minutos.',
        'knowledge-02':'Invierte la relación de latencia local/Internet y distancia.',
        'knowledge-03':'Incluye explicaciones científicas contradictorias: hielo más compacto, sal impide flotar y agua cambia por miel.',
        'knowledge-06':'Sustituye la diferencia entre programa bloqueado y cerrado por gestión de señales de cierre.',
        'knowledge-08':'Agota32768tokens sin respuesta visible (finish_reason=length).',
        'instruction-04':'Traduce primera persona como He; cambia el sujeto exigido.',
        'instruction-08':'Generaliza que file-not-found hace que el programa deje de funcionar; no se deduce de ese error. La posible causa de permisos y el ejemplo tipográfico no son por sí solos la razón del fallo.',
        'context-03':'Responde20GiB usados en vez de13 tras la corrección.',
        'context-06':'Termina sin respuesta visible; no formula la aclaración solicitada por la ambigüedad.',
        'context-10':'Afirma que un HDD suele consumir500W o más.'
    },
    '37-q4-high-reference699':{
        'facts-04':'Convierte volumen42 en amplitud medida y añade una interpretación de señal analógica no observada.',
        'facts-09':'Degenera en prosa incoherente y marcado interno; afirma IPv4 de4bits y extrae falta de Internet de un timeout.',
        'facts-15':'Descarta el dato not charging proporcionado e inventa que el informe no es fiable en vez de responder conforme a la premisa.',
        'facts-18':'Reconoce que falta lectura actual pero asegura que cambió y añade os.cpu_percent, una API inexistente.',
        'facts-19':'Invierte el significado de espacio libre y responde375GB en vez de125GB.',
        'knowledge-02':'El ejemplo de otro router conectado a Internet se usa para afirmar ausencia de Internet sin fundamento.',
        'knowledge-03':'Incluye explicaciones científicas incorrectas y prosa degenerada sobre flotación del hielo.',
        'knowledge-06':'Reinterpreta no responde como estado idle/cierre limpio y añade afirmaciones falsas de cierre y guardado.',
        'knowledge-10':'Añade que un endpoint read-only sólo recibe POST y no puede enviar GET; ejemplo técnico materialmente incorrecto.',
        'context-08':'Ignora la duración corregida y responde18:15 en vez de17:55.',
        'context-10':'Añade acceso RAM en fracción de nanosegundo y confunde traer datos ausentes con page-out, aunque después describe page-in correctamente.'
    },
    '37-q4-high-practical699':{
        'facts-01':'Añade que usada excluye cachés y buffers y lo atribuye a una definición estándar Windows sin que se deduzca del ejemplo.',
        'facts-04':'Convierte volumen configurado en señal de energía y propone semánticas de detector no observadas.',
        'facts-05':'Inventa falta de permiso para ver la ventana y requisitos .NET de navegadores/Word98.',
        'facts-09':'Convierte el timeout en confirmación de Internet caído y añade prosa/instrucciones incoherentes.',
        'facts-14':'El código trata la existencia del documento como prueba de este guardado y añade heredoc sobrescrito como causa no sustentada.',
        'facts-18':'Responde40% como CPU actual a partir de una lectura antigua.',
        'knowledge-03':'Explicación científica incoherente; llega a afirmar que el hielo flota por ser más denso.',
        'knowledge-04':'Añade una referencia inventada a Black Mesa y altera zorpos por zorros aunque responde verde.',
        'knowledge-06':'Cambia la pregunta por CPU apagada y enseña estados incorrectos de programas/ventanas.',
        'knowledge-07':'Afirma que VRAM sólo puede ser utilizada por la GPU, excluyendo su acceso desde CPU.',
        'context-06':'Pregunta sobre criterios de comparación en vez de cuál aplicación abrir.',
        'context-10':'Repite una instrucción de traducción en vez de explicar RAM y disco en inglés.'
    },
    '37-q4-low-practical699':{
        'facts-04':'Invierte silenciado sí a no silenciado y añade que está encendido sin observación.',
        'facts-05':'Responde principalmente en inglés a la petición española, con inicio corrupto.',
        'facts-06':'Inventa una historia de telemetría/sensores y degenera en varios idiomas.',
        'facts-08':'No comunica el registro; pide instrucciones de configuración ajenas a la pregunta.',
        'facts-09':'Añade causas de conectividad inventadas/incoherentes como AD-ANTONA USB/bluetooth.',
        'facts-11':'Responde sobre permisos de10MB en vez de ordenar los procesos.',
        'facts-15':'Inventa una Nintendo Switch y explica not charging como carga lenta; descarta el dato explícito.',
        'facts-17':'No entrega respuesta visible con finish_reason stop.',
        'facts-20':'No interpreta muted:true; pide aclarar una pregunta que ya contiene los datos.',
        'knowledge-02':'Añade hechos inventados sobre servidores externos viendo nombres/dispositivos y sphere of control.',
        'knowledge-03':'Prosa incoherente, marcado interno y explicación científica falsa de estructura/densidad.',
        'knowledge-04':'Sustituye la premisa por una canción inventada y responde marrón en vez de verde.',
        'knowledge-09':'Calcula11:03 en vez de10:15.',
        'instruction-02':'Contexto claro no resume ninguna cifra solicitada.',
        'instruction-04':'Cambia no he borrado por una petición futura de no borrar.',
        'instruction-05':'Responde Lila en vez del penúltimo Cobre.',
        'instruction-09':'Responde9 en vez de27.',
        'instruction-10':'Entrega marcado de una herramienta inventada sin la traducción visible solicitada.',
        'context-01':'Añade cifras contradictorias, comandos y explicaciones de almacenamiento inventadas.',
        'context-04':'La frase no conserva claramente que falta una nueva lectura; no there is a newer reading altera la negación solicitada.',
        'context-06':'Entrega marcado interno de una herramienta inventada en vez de aclarar qué aplicación.',
        'context-07':'Afirma que120MB es la mitad de300MB.'
    },
    'qwen-q4-practical699':{
        'facts-04':'Confunde volumen configurado con señal sonora medida y presenta el mute como contradicción/error de captura.',
        'facts-08':'Afirma reproducción activa a partir de no silenciado y volumen35%, sin observación de reproducción.',
        'facts-15':'Contradice not charging y termina afirmando que probablemente sí carga.',
        'facts-20':'Interpreta muted=true como no silenciado y afirma que está sonando.',
        'knowledge-02':'Afirma que ver una red en el menú significa estar conectado; también infiere acceso a redes sociales de conexión Wi-Fi.',
        'knowledge-06':'La tabla afirma que un programa cerrado no puede abrirse de nuevo porque está cerrado.',
        'knowledge-07':'Afirma que VRAM es exclusiva de renderizado, vídeo y efectos3D, excluyendo otros cómputos GPU.',
        'instruction-08':'Traduce la pregunta en vez de explicar file not found.',
        'instruction-09':'Añade una oración cuando sólo se pidió el número.',
        'context-06':'Sustituye aclarar cuál aplicación por preguntar sobre una comparación y su dominio.'
    },
    'qwen-q4-reference699':{
        'facts-09':'Afirma que la navegación de otro dispositivo en la misma red basta para confirmar Internet en el dispositivo consultado.',
        'facts-14':'Concluye que el documento no se guardó y posiblemente se perdió, sin comprobarlo tras el timeout.',
        'facts-15':'Contradice not charging y termina afirmando que sí carga.',
        'facts-18':'Responde40% como uso actual basándose en una lectura antigua.',
        'facts-20':'Interpreta muted=true como no silenciado y afirma que está sonando.',
        'knowledge-06':'Ejemplifica cerrar una pestaña de Chrome como si el programa ya no estuviera activo; confunde pestaña y proceso.',
        'knowledge-07':'Afirma que VRAM se usa exclusivamente para gráficos, excluyendo otros cómputos de GPU.',
        'instruction-08':'Traduce la pregunta al español en vez de explicar el significado solicitado.',
        'instruction-09':'Da una oración explicativa cuando se pidió únicamente el número.',
        'context-06':'Sustituye el pedido ambiguo de abrir el otro por un análisis comparativo; no aclara cuál de las tres aplicaciones.'
    }
}
assert a.tag in manual, 'No complete manual review registered for this profile'
private=Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-k2-native699-{a.tag}-private'
out=base/f'run-{a.tag}'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
panel=read(base/'PANEL.json')
records=[json.loads(x) for x in (private/'results.jsonl').read_text(encoding='utf-8').splitlines()]
metrics=read(out/'MEASUREMENTS.json')
assert len(panel)==len(records)==50 and metrics['results_sha256']==sha(private/'results.jsonl')
assert [r['id'] for r in panel]==[r['case'] for r in records]
assert set(manual[a.tag])<={r['id'] for r in panel}
rows=[]
report=[f'# Respuestas originales: {a.tag}', '',
    '50 controles sintéticos; no contienen turnos históricos del dueño. Sólo respuesta visible, sin razonamiento interno. Adjudicación manual por hechos, idioma y formato fijados antes de inferencia. No es aceptación de C03.', '']
for row,record in zip(panel,records,strict=True):
    verdict=dict(id=row['id'],group=row['group'],language=row['language'],
        passed=row['id'] not in manual[a.tag],reason=manual[a.tag].get(row['id'],'Cumple la rúbrica fijada.'),
        answer_sha256=hashlib.sha256(record['content'].encode()).hexdigest(),
        seconds=record['seconds'],finish_reason=record.get('finish_reason'))
    if record.get('error') or not record['content'].strip() or record.get('finish_reason')=='length':
        assert not verdict['passed'], row['id']
    rows.append(verdict)
    report.extend([f'## {row["id"]} — {"cumple" if verdict["passed"] else "falla"}', '',
        '**Conversación enviada:**',''])
    for message in row['payload']['messages']:
        report.extend([f'**{message["role"]}:** {message["content"]}', ''])
    report.extend(['**Respuesta visible:**','',record['content'] or '*(Sin respuesta visible)*','',
        '**Rúbrica:** '+row['rubric'],'','**Adjudicación:** '+verdict['reason'],'',
        f'Tiempo: {record["seconds"]:.3f} s. Terminación: {record.get("finish_reason")}.',''])
notes={
    '37-q4-high-practical699':'All50 visible finals read. facts08 accepted: the PANEL explicitly states a preceding mute request; this is not an invented action. Conditional failure/early-reading hypotheses do not assert success. facts15 preserves not-charging versus plugged-in; loose voltage discussion not treated as a contrary battery-state conclusion. knowledge01/02 central distinction accepted without demanding exhaustive hardware/network detail. knowledge07 only-usable-by is a stronger incorrect access restriction than low used-by wording. instruction08 describes possible program stopping conditionally, unlike BF16 unsupported generalization; minor directory/example wording not independently failed. context09 repeats the explicit no-action premise. Peer review agreed through context05 after correcting its mistaken reading of facts08; root reviewed final5.',
    '37-q4-low-practical699':'All50 finals read. facts03 accepted: despite unnecessary ambiguity claim it uses the explicitly free50GB and computes75%. facts10 reviewed-your-files interpreted as reviewing the provided example sizes, with no new filesystem finding. facts14 likely-not remains explicitly unconfirmed. knowledge01/06/10 preserve the central distinction despite weak prose; not every awkward word is a failure. knowledge07 accepted: exclusively by the graphics processor attaches to the processor, not an unequivocal graphics-only claim. context09 accepted as repeating the supplied no-action premise, consistently with other profiles. context04 fails because the negation is not preserved clearly. Peer preferred failing knowledge07/context09 but accepting context04; this is a disclosed one-point net judgment difference (27 versus28), not hidden exclusions.',
    'qwen-q4-practical699':'All50 visible finals read. facts05 accepted as an unsuccessful opening attempt with access error; no explicit observed-closed state. facts14 retains likely-not uncertainty and demands verification, accepted consistently with K2 reference. instruction01 keeps lack of permission and inability to access, despite changing person and omitting a literal I-could-not-open phrase; not graded by exact wording. context09 same interpretation as Qwen reference. facts08 differs materially from the ambiguous reference answer: this profile explicitly asserts active playback and therefore fails.',
    '37-q4-high-reference699':'All50 visible finals read. Facts14 accepted because the final explicitly leaves saving unconfirmed despite poor likely-not calibration; facts20 accepted because the explanation correctly preserves the mute override despite calling the inputs inconsistent. Knowledge07 does not assert graphics exclusivity. Instruction01 future retry intention accepted as a rewrite with no false success, consistent with BF16 context05. Context06 asks which of the three apps despite minor comparison wording; context09 repeats the supplied no-action premise rather than claiming a new filesystem inspection. Materially wrong extra facts fail even when the core definition is initially correct. Peer agrees through context09; context10 final reviewed by root.',
    '09-bf16-high-reference699':'Minor understandable wording accepted (facts02,knowledge07,knowledge10); conditional hypotheses in facts06 accepted. Context05 is a future-tense acknowledgement but makes no false execution claim and meets its frozen rubric. Extra materially wrong facts do fail, even after a correct opening. Instruction08 is judged by its unsupported generalization that the program stops functioning, not merely by possible permissions issues.',
    'qwen-q4-reference699':'All50 finals read manually. facts08 accepted: activo/con sonido is interpreted as enabled/unmuted, consistent with its explicit no-mute explanation; it does not explicitly assert current media playback. A second reader preferred failure, so this is a documented judgment difference (39 vs40 under that stricter reading), not a hidden exclusion. knowledge02 accepted as a contextual Wi-Fi explanation without requiring an exhaustive topology list. context09 ensured is interpreted as refraining from deletion, not claiming a filesystem inspection. Equivalent tolerance for understandable wording used for BF16.'
}
if a.tag == 'qwen-q4-practical699':
    notes[a.tag] += ' Peer preferred failing context09 as an unsupported verification; root retains the same no-action interpretation used for the reference. Disclosed judgment difference39 versus40.'
result=dict(utc=datetime.now(timezone.utc).isoformat(),tag=a.tag,passed=sum(r['passed'] for r in rows),
    failed=sum(not r['passed'] for r in rows),cases=50,rows=rows,panel_sha256=sha(base/'PANEL.json'),
    raw_results_sha256=sha(private/'results.jsonl'),measurements_sha256=sha(out/'MEASUREMENTS.json'),
    scope='Complete manual development review of visible finals, not blind or a general-model benchmark. Does not grant survey/C03 coverage.',
    review_notes=notes[a.tag],
    by_group={group:dict(passed=sum(r['passed'] for r in rows if r['group']==group),cases=sum(r['group']==group for r in rows)) for group in Counter(r['group'] for r in rows)},
    by_input_language={lang:dict(passed=sum(r['passed'] for r in rows if r['language']==lang),cases=sum(r['language']==lang for r in rows)) for lang in Counter(r['language'] for r in rows)})
(out/'ADJUDICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'RESPUESTAS.md').write_text('\n'.join(report),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','review_notes']},ensure_ascii=False))
