"""Preserve unadopted source and record measured continuation state."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-window-projection667'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p,v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
assert not (out / 'CANDIDATE.patch').exists()
(out / 'CANDIDATE.patch').write_bytes(subprocess.check_output(['git','diff','--','src/baxy_mind/llm.py'], cwd=root))
(out / 'CANDIDATE_TEST.py').write_bytes((root / 'tests/test_c03_window_prose_projection.py').read_bytes())
log = Path(os.environ['TEMP']) / 'c03-window-projection667-refined.log'
assert '439 passed' in log.read_text(encoding='utf-8-sig')
(out / 'FOCAL.log').write_bytes(log.read_bytes())
write(out / 'RESULT.json', {'adopted':False, 'source_sha256':sha(root / 'src/baxy_mind/llm.py'),
    'test_sha256':sha(root / 'tests/test_c03_window_prose_projection.py'), 'focal_passed':439,
    'native668_original_correct':10, 'native668_original_total':10, 'native668_compound_correct':0,
    'native668_compound_total':4, 'product669_correct':24, 'product669_total':24,
    'limits':'Native670 still confuses normal/visible with focus. Not adopted. No owner suite, declaration refresh or Fast for667 yet. No final Full or joint UI/voice acceptance.'})
write(out / 'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-window-projection667/** -text\n')

note = '''# C03 — estado vigente tras670

Goal activo en Goal-c03; main intacto5f572ee1b48cb5e2543ee5e06510e51057c9c845. Objetivo completo: C:/Users/usuario/.codex/attachments/b424eff2-0702-4cc9-871a-451d31ecf314/goal-objective.md. Sin subagentes ni decisión pendiente. Conservar otra tarea del dueño en VS Code y sus cambios.

Fuente publicada660: db47edca6f521e29ca102b830b2134f3489337b9; últimos documentos publicados antes de este tramo ad100b189ef4861d72a7a1346c590743ae079310. No usar main. Fuente667 es WIP no adoptado: llm.py y tests/test_c03_window_prose_projection.py. Cambia únicamente el nombre booleano foreground a is_current_window_for_user_interaction en la proyección de prosa, preservando la observación canónica. Copia exacta de patch/test y focal439 pases en astra-window-projection667; prototipo inicial incorrecto in_front_of_other_windows conservado aparte. Pins actuales de V8/STT todavía corresponden660: actualizar sólo al validar/adoptar la candidata, sin cambiar sellos históricos.

668:28 borradores EOS. Diez controles anteriores baseline9/10→candidata10/10, paridad exacta del builder. Cuatro controles nuevos separan foco de always-on-top: ambos0/4. 670 localiza la confusión: nativo mínimo1/4, identidad0/4, compositor0/4; los cuatro completos reproducen668. El nativo equipara normal/visible con foco. Matiz: not(A and B) inglés no es necesariamente negación de A; razón corregida en670, score668 intacto. No añadir otra instrucción equivalente: siguiente contraste factual existente para estados de ventana, con sujeto/negación y pruebas del compositor real. No otro narrador ni respuestas fijas.

669 producto:24/24 con22 observaciones y snapshots independientes,24 actividades iguales a finales. Foco real en español reparado. Steam/WhatsApp cerrados ahora: no prueba sus estados positivos de661/665 ni reparación de un ventana. RAM1904,250MiB/GPU3497,559MiB/45,187s sin infracciones; sin UI/voz ni comparación emparejada de ahorro. 668 RAM719,086MiB/18,282s;670 RAM722,902MiB/17,234s; mismo GPU3497,559MiB. Registro intacto.

RAM del PC: Steam, Discord y WhatsApp cerrados por petición expresa, procesos verificados ausentes. Disponible1,167→2,876GiB en el tramo de liberación; antes6693470,3MiB. Se preservaron VS Code con otra tarea activa, ChatGPT, Opera y Chrome. No eludir el bloqueo anterior de Computer Use sobre Opera. BAXY manual debe permanecer cerrado; diagnóstico permitido. No campaña viva: sesiones51412/79494/72533 recogidas exit0.

Encuesta742/rev1248:26 cubiertos/716 abiertos/0NA, sin cambios este tramo. SHA237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7. Histórico/nuevos autorizados por536, sin bloqueo de frescura. Faltan cobertura, ocho rutas, UI real, loopback íntegro/AEC separado, avería→restauración→normal y Full final. ContinuidadC04–C09 documentada; no ejecutar sus goals. Voz humana física/wake/FAR/FRR sonC08.

Full651 es sólo baseline anterior:10411 pases/3skips ambientales+466subtests; .NET4469pases/1skip agregado y16 opt-in aparte. No Full667. Regla del objetivo: Full cuando se adopta C#+Python juntos y cierre final, no cada edición Python. Fuente660:4046 dueñas+121subtests/0skip, declaraciones22pases/1skip ambiental, Fast0; no atribuir esas pruebas a667.

RuntimePython C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8. Qwen3-4B-Instruct-2507Q4_K_M y llama b9980 intactos. Manifest SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed. No solapar inferencia/build/Full.

Scripts preserve667, native668, close668, product669, close669, native670, close670 y record667-670 YA ejecutados; no repetir. Artefactos sellados -text, privados con payloads/respuestas literales y adjudicación. Auditar/publicar sólo la evidencia y estos scripts antes de otra fuente; conservar WIP667 hasta resolver aceptación o rechazo. Goal no completo.
'''
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
state_path = base / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8-sig'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='667 WIP439 focales;668 original10/10 y compuestos0/4;669 producto24/24;670 nativo1/4. No adoptada.',
    continuation='Auditar/publicar evidencia667-670 sin adoptar fuente667. Siguiente: contraste factual de estados separados; nativo ya confunde normal/visible con foco. Ver HANDOFF. BAXY cerrado.',
    previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='RAM liberada y verificada;668/669/670 completadas y adjudicadas, con primer error nativo localizado. No decisión pendiente.',
    activeValidation=None)
write(state_path, state)
print({'candidate_preserved':True, 'goal_active':True, 'source_adopted':False})
