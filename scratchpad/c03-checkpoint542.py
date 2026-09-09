from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-gpu-scope542'
text='''# C03 — alcance GPU y RAM542

Se adopta la distinción compartida entre memoria de video y RAM. La consulta inglesa de GPU de541 ya no cuenta como dos alcances incompatibles; una petición que añade RAM explícitamente sí conserva ambos. Seis variantes ES/EN y tres controles mixtos amplían la prueba dueña; ocho fallaban antes de editar, junto a43pass.

Validación: `test_system_status_scope_grounding.py test_machine_status_scope.py test_effect_intent.py`:1917pass/0skip,45,50s. `test_turn_policy.py test_generalization_product_r6_development.py test_stt_quality_evaluators.py`:1628pass/1skip ambiental,8,63s. El skip es la campaña ciega STT sin sus archivos, no una aceptación de voz. Fast verde completo; Release19,55s,0warnings/0errors. No cambio C#; no procede repetir Full por esta edición. Full final sigue pendiente.

Sólo cambia effect_intent.py y sus pruebas, más las dos declaraciones del árbol de programa actual para STT. Hash actual69586e40ec78f1ac4b183575f110f36371633b02b17d3bc52516a92cf4952086,403archivos; sellos de campañas históricas intactos. Sin cambios de modelo, runtime o prosa prefabricada.

Límite: reparación de alcance, no certificación del resultado final. La prosa española de541 confundió6287261696bytes dedicados con8GB; ese fallo es independiente y sigue abierto. También siguen memoria desactivada/capacidad, metadatos de guardado, discos plurales, curiosidades no verificadas y distinción de núcleos lógicos. Producto siguiente: comprobar los argumentos y hechos GPU reales con la fuente nueva antes de tocar su presentación.

Encuesta:3cubiertos/739abiertos/0no aplicables, sóloH0002/H0016/H0021 acreditados con casos y variantes reales541. La corrida541 conservó25finales de44; se cortó correctamente por RAM libre del sistema inferior a768MiB. GPU3499,559MiB/RAM2430,715MiB, sin UI/voz. No se atribuye aceptación a las19entradas no ejecutadas.
'''
(out/'RESULT.md').write_text(text,encoding='utf-8')
with (base/'CHECKPOINT.md').open('a',encoding='utf-8') as handle:
    handle.write('\n\n## Tramo542 — alcance GPU y primeras conductas acreditadas\n\n'+text.split('\n\n',1)[1])
(base/'HANDOFF.md').write_text('''# Handoff C03 —542

C03 EN_CURSO, ramaGoal-c03, tarea01a07974-2a33-7ed3-ba87-2436944e8115. La decisión536 del dueño permite históricos y nuevos; no queda pendiente aclaración de frescura. El goal API sigueblocked y no tiene herramienta para reanudar; el trabajo está autorizado y continúa. Main intacto. Sin subagentes. BAXY manual cerrado; encuesta original preservada.

Fuente: effect_intent542 distingue video/graphics/GPU memory y memoria gráfica/de video/de la GPU de RAM; conserva una petición independiente de RAM. __main__530,llm520,C#516 intactos. Owners1917pass0skip+1628pass1skip ambiental STT; Fast542verde/Release19,55s0warnings/errors. Árbol STT actual69586e40ec78f1ac4b183575f110f36371633b02b17d3bc52516a92cf4952086/403archivos, campañas históricas intactas. Commit/push de esta fuente trascheckpoint; verificar HEAD remoto. Full526 rojo tenía25fallos resueltos por dueñas528–531; finalFull pendiente, no repetir salvo adopción C#+Python o candidato final.

Encuesta:3cubiertos/739abiertos/0no aplicables. H0002(capitales),H0016(biografías),H0021(identidad) tienen literal y variantes reales541; no inferir crédito para similares. Registro privado336 y resumen público actualizados.541 programó44turnos de20casos:25finales;19no ejecutados por corte de RAM libre menor768MiB. Perfil aislado, runtime registrado, sin UI/voz; GPU3499,559MiB/RAM2430,715MiB/96,985s. No procesos BAXY/llama restantes al comprobar trascorte. Informe privado C03-survey-readonly541-private/RESULT.md; detalles y hashes públicos astra-survey-readonly541/RESULT.json.

Fallos541 prioritarios: VRAMdedicada6287261696bytes narrada8GB; consultainglesaGPU+video memory produjo summary sinadapters, arreglada la causa léxica542 pero pendiente repetirproducto; discolibrepluralES rechazado aunqueEN correcto; curiosidades gratuitas;16procesadoreslógicos llamadosnúcleos sincalificar;95%batería llamadoya cargada. H0040Steam/Spotify frasescorrectas pero falta comprobarobservaciones porinvocación. H0041raíces12/15correctas, varianteEN81 noejecutada: grupoabierto.

537–540 cerrados sinadopción: descripcionescatálogo, contratoglobalderelevancia, selectorverificado, cláusulaexistencia/configuración. Ningunoarreglaguardado; variosañadenafirmacionessobrecontenidosensible.537watchdogTypeErroralcompararGPUinitialNone; recursosmuestreadospero noacreditavigilancia.538–540corrigenesperaacotadatelemetría. No repetirprompts/flags/selector sincausanueva. Siguenfallos521guardadometadatos y memoria desactivada≠funcióninexistente.

SIGUIENTE: confirmar enproductoque542elige gpu_identity enES/EN, conservar y examinarhechosantesdeprosa. Corregir conversión debytes/VRAM enel dueñodepresentación y exigir que no use RAMcompartidacomodedicada. Hay~3GBRAMlibre: no levantarotroproducto a la vezquecompilación, ni cerrarappsdelusuario. Continuar19turnosnoejecutados541 enunperfilnuevo conprocedencia/contextoexplícitos; no repetir25yaobservadossinnecesidad. Después cobertura742/ochorutas, UIrealdedesktop, loopbackcompleto/supresiónAEC, recursosconjuntos, finalFullverde. Vozhumana/wake/FAR-FRRC08conhandoff, no cerrarfilasajenas.
''',encoding='utf-8')
relevo_path=base/'RELEVO_ACTIVO.json'
relevo=json.loads(relevo_path.read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
              checkpoint='542: alcance GPU/RAM corregido, dueñas/Fast verdes; encuesta3cubiertos/739abiertos/0NA.',
              continuation='Confirmar GPU en producto, reparar prosa de capacidades medidas y continuar variantes/encuesta/UI/voz/Full. No espera por dueño.',
              surveyVerificationCounts={'covered':3,'open':739,'not_applicable':0})
relevo_path.write_text(json.dumps(relevo,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for directory in (out,base/'astra-survey-readonly541'):
    pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file() and p.name!='PINS.json'}
    (directory/'PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
print('Checkpoint542 written; source validation and survey3/739/0 preserved.')
