from pathlib import Path
from datetime import datetime, timezone
import json

base=Path(__file__).resolve().parents[1]/'artifacts/comprobaciones/C03'
checkpoint='''# C03 — checkpoint307 — EN_CURSO

Fuente307 adopta solicitud literal en _compose_user_content: retira la cita interna
«Texto original de la persona» conservando texto, hechos, idioma y reintentos.
303 añadir subject a identidad falló;304 roles user/assistant/tool funcionaron;
305 aisló que basta solicitud literal, sin nueva arquitectura. Corrigió un error
de fixtures303/304 (doble barra en qualifiedName).306 nueve controles de rutas:
mejora identidad y nivelvolumen, no regresiones semánticas observadas; confirmación
aún dice «cerrazón» y explicación tiene «ciertos bacterias», ambos defectos vigentes.

307: baseline3fail43deselected0,54s (primer error de pytest request reservado
corregido y preservado). Tres suites1025pass0skip8,81s; presentación/voz180pass,
0skip1,96s. Native307 código real sin parche coincide payload306 y produce
«Tú eres usuario, usuario del dominio REDNOTE.»; causaUTF8 también conservada.
Fast308 EN EJECUCIÓN session9382, astra-request-speaker307/fast308.log.
ÚltimoFastverde299. No Full de reparación. .NET2991879pass0skip2m25s.

UI302 DETENIDA para Fast308 tras verificar sólo bienvenida t0, cero turnos del
dueño y /slots libre; logs privados C03-ui302-snapshot308. App91968/backend93444
ya no activos. SIGUIENTE: terminar Fast308, prueba --ui-probe309 de un único
«quien soy», leer DOM/resultado real sin contar progreso ni sólopublished como éxito;
reabrir BAXY310 sin probe/timer. No dejar cerrado al entregar.

Fuente298/299 mantiene reparación de saludo real: producto301 publicó
«Hola Emmanuel, ¿cómo estás? 😎» sin memoria.save. Journal sólo memory.status.
Lima301 NO útil: primera bruta inventa haber viajado, retry sóloLima; sigue pendiente.
300 perfil anidado inválido,301corrige hijo directo sin relajar privacidad.

Sesiónhumana264 completa121mensajes(63dueño58BAXY), TRANSCRIPT282.json/.md privado
%LOCALAPPDATA%/BAXY/C03-owner264-heap280. No subir dump/textocompleto.
Cuestionario742 http://127.0.0.1:63179/ PID101140 disponible sin temporizador;
answers.json en C03-owner-questionnaire-20260907 es del dueño: no rellenar,
sobrescribir ni congelar. Tres ingleses admitidos vigentes. No agentes paralelos.

Goal-c03/HEAD2bf3d4c preservar WIP/main. Modelo2507registrado no promovido.
Pendientes todos criterios completos: otras rutas/contexto/capacidades/errores,
París,100/100humanos frescos sin congelar, recuperación, UI/voz/ASR/recursos,
runtime/instalación,continuidadC04–C09, Full y publicación fuera main.
Últimos recursos2603516,66MiBGPU4822,60MiBRAM conAEC/Piper sinASRhumano;
wake sincertificar. Sin bloqueoexterno. Tramo previo fue progreso, no cierre.
'''
for name in ('CHECKPOINT.md','HANDOFF.md'):
    (base/name).write_text(checkpoint,encoding='utf-8')
path=base/'RELEVO_ACTIVO.json'
row=json.loads(path.read_text(encoding='utf-8'))
row.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='307: literal user framing adopted;1205 owner tests pass; native identity correct. Fast308 running,UI302 stopped with preserved logs.',continuation='Collect Fast308,run one actual UI probe309 and reopen BAXY310. Whole C03 remains active.')
row['userOwnedInstance'].update(status='stopped_for_Fast308',processRevalidated=False,instruction='UI302 stopped with only welcome and no owner turns. Reopen after Fast/UI check; questionnaire remains alive.')
path.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
