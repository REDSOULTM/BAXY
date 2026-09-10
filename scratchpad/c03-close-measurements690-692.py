"""Seal all paired numeric drafts and the whole-survey planning board."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
helper=(root/'scratchpad/c03-seal-614-615.py').read_text(encoding='utf-8')
exec(compile(helper[:helper.index("out = base/'astra-gemma-product614'")],__file__,'exec'))

installed={'H0111','H0162','H0539','H0655','H0508','memory-total-en'}
raw_failures={
 'H0384':'Reports available and total but omits the requested used space.',
 'H0026':'Claims 8 GB dedicated VRAM, unsupported by the observed dedicated capacity.',
 'H0114':'Claims unmeasured adapters are not in use; engine usage is not VRAM occupancy.',
 'gpu-usage-es':'Reports engine utilization as dedicated memory utilization.',
 'H0342':'Says used RAM cannot be known despite total and available from the same snapshot; calls usable memory installed.',
 'memory-used-es':'Omits requested used RAM despite derivable quantity.',
 'memory-used32':'Omits requested used RAM despite derivable quantity.',
 'memory-full16':'Reports zero available but omits requested used amount.',
 'gpu-engine92-memory12':'Reports 92 percent engine usage as VRAM occupancy; observed occupancy is 12.5 percent.',
 'gpu-usage-unmeasured':'Claims capacity is current VRAM usage although usage was not measured.',
}
binary_failures={k:'Labels a binary GiB quantity as GB or gigabytes.' for k in
                 ['H0194','H0625','H0111','H0162','H0539','H0655']}
binary_failures['H0114']='Correct dedicated memory occupancy but additionally claims an unmeasured AMD adapter is inactive.'
old_rows=rows(home/'C03-native-measurements690-private/responses.jsonl')
old={(r['case_id'],r['arm']):r['response']['choices'][0]['message']['content'] for r in old_rows}
for number,label in [(690,'measurements'),(691,'measurement-units')]:
    private=home/f'C03-native-{label}{number}-private'
    out=base/f'astra-native-{label}{number}'
    assert not (out/'RESULT.json').exists()
    panel={(r['case_id'],r['arm']):r for r in read(private/'panel.json')}
    responses=rows(private/'responses.jsonl')
    assert len(panel)==len(responses)==60
    resources=read(out/'RESOURCES.json')
    assert resources['complete'] and resources['manifest_unchanged'] and not resources['violations']
    controls=0;adjudication=[]
    for r in responses:
        case=panel[r['case_id'],r['arm']]
        choice=r['response']['choices'][0]
        assert choice['finish_reason']=='stop'
        draft=choice['message']['content']
        failures=raw_failures if r['arm']=='current_bytes' else (
            {} if r['arm']=='decimal_quantities' else binary_failures)
        verdict='failed' if r['case_id'] in failures else (
            'needs_verification' if r['case_id'] in installed else 'correct_observed_fixture')
        reason=failures.get(r['case_id'],
            'Installed versus OS-usable capacity is not observed separately in this fixture; do not award survey coverage.'
            if r['case_id'] in installed else
            'Reviewed against complete fixture: requested quantity/identity, units, language and unknowns are supported, with displayed rounding.')
        if number==690 and r['arm']=='current_bytes' and case['original_draft'] is not None:
            assert draft==case['original_draft'];controls+=1
        if number==691 and r['arm']=='binary_quantities':
            assert draft==old[r['case_id'],'typed_quantities'];controls+=1
        adjudication.append({'case_id':r['case_id'],'arm':r['arm'],'text':case['text'],
            'draft':draft,'verdict':verdict,'reason':reason,'origin':case['origin']})
    assert controls==(24 if number==690 else 30)
    write(private/'adjudication.json',adjudication)
    report=[f'# Comparación nativa {number}: todas las respuestas']
    for r in adjudication:
        report+=['## '+r['case_id']+' · '+r['arm'],r['text'],r['draft'],r['verdict']+': '+r['reason']]
    (private/'RESULT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8')
    counts={arm:dict(Counter(r['verdict'] for r in adjudication if r['arm']==arm)) for _,arm in panel}
    if number==690:
        note='''# 690 — cantidades explícitas; conversión binaria insuficiente

30casos por dos representaciones,60EOS; los24controles históricos reproducen exactamente los primeros borradores689. RAM usada, disco ocupado y ocupación de VRAM mejoran al derivar cantidades, pero varias salidas etiquetan GiB como GB y una GPU no medida sigue descrita como inactiva. Se conserva cada fallo; no se adopta el brazo binario ni se acredita encuesta.

La preparación inicial falló antes de lanzar el modelo al intentar decodificar la copia de auditoría de situation limitada a2048caracteres. PREPARATION_ERROR.log se conserva. Eso no demuestra que la petición real estuviera truncada: se usó el payload completo registrado y se comprobó su reconstrucción por los24borradores idénticos. Se corrigió explícitamente la afirmación inicial al dueño. GPU3499,559MiB/RAM728,270MiB/28,422s; sin infracciones. Sin UI/voz ni cambio de registro.
'''
    else:
        note='''# 691 — unidades decimales conservan el significado numérico

Mismos30casos, dos brazos,60EOS. Los30controles binarios reproducen690 exactamente; cambiar sólo divisor y etiqueta aGB elimina las etiquetas binarias erróneas y conserva el12,5%VRAM frente al92%de uso del motor.24casos cumplen el fixture y seis consultas de capacidad RAM siguen pendientes de distinguir instalada de utilizable. No se infiere RAM instalada del total del sistema operativo.

GPU3497,559MiB/RAM720,449MiB/40,141s, sin infracciones ni cambio de registro. Evidencia para el candidato compartido693, todavía sin adopción ni cobertura nueva. Los742requisitos se planifican juntos en COVERAGE_WORKBOARD692.json:26cubiertos/716abiertos. Las515filas sin resolución estática autónoma requieren contexto o modelo; no son515fallos demostrados. Ninguna fila se marca cubierta por pertenecer a una categoría.
'''
    seal(out,private,{'utc':datetime.now(timezone.utc).isoformat(),'cases':30,'responses':60,
        'all_finish_stop':True,'exact_control_reproductions':controls,'counts_by_arm':counts,
        'resources':resources,'source_adopted_by_this_experiment':False,'survey_coverage_added':0,
        'ui_or_voice_credit':False,'goal_complete':False},note,
        ['panel.json','requests.jsonl','responses.jsonl','adjudication.json','RESULT.md'])
    print(number,counts)
write(base/'COVERAGE_WORKBOARD692_PINS.json',{'COVERAGE_WORKBOARD692.json':sha(base/'COVERAGE_WORKBOARD692.json'),
    'scratchpad/c03-coverage-workboard692.py':sha(root/'scratchpad/c03-coverage-workboard692.py')})
with (root/'.gitattributes').open('a',encoding='utf-8') as stream:
    stream.write('/artifacts/comprobaciones/C03/COVERAGE_WORKBOARD692*.json -text\n')
