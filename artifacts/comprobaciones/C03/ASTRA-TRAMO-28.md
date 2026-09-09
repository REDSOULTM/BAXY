# C03 — tramo28: límites tipados y continuidad

EN_CURSO, sin bloqueo externo. Turno anterior: progreso (reversión de experimento
fallido, pruebas y reporte literal). Este tramo no reabre entrenamiento ni modelos.

## Comprobado

- Redactor existente de error/out_of_catalog:9/9 casos consumidos útiles con
  Qwen base, sin inferir inexistencia. astra-boundary-composer-qwen-base.
- _prepare_turn_result reutiliza ese redactor sólo para límite de identidad del
  catálogo. Otras conversaciones no cambian. Tres pruebas de frontera añadidas.
- astra-boundary-product-qwen:12/12publicados,61,11s,GPU3499,56MiB. Caso inglés
  ahora dice «This is outside what I do on this PC.» sin causa inventada. La
  aclaración mixta todavía carecía de estado pendiente; no es12/12aceptación.
- 1157pass +115subtests,6,60s, suites turn_policy/c03_request_preservation/
  compose_contract/planner. Test antiguo de opciones usaba ambas opciones
  «Confirmar / cancel» como si faltara una; ahora omite de verdad cancelar y
  exige al menos2llamadas. No se relaja el requisito de ambas opciones.
- astra-clarification-continuation-qwen:12turnos,11publicaciones,74,11s,
  GPU3499,56MiB. Español80% aplicado; inglés60% aplicado pero prosa agotada;
  mixto40% no aplicado por pérdida de aclaración. Restauración100% leída en t12.
- astra-product-default-kv-qwen:21turnos,19publicados,71,08s,GPU3067,56MiB.
  KVq4 por defecto introduce audio invertido, reunión inventada y2confirmaciones
  agotadas. Se rechaza ese perfil para promover Qwen. Qwenq8 sigue candidato;
  registro Granite intacto. No atribuir toda diferencia a KV sin reconocer
  muestreo/historial vivos y fuente actualizada en la ruta de catálogo.

## Correcciones actuales, verificación pendiente

Inglés60%: borrador correcto «I set the volume to 60%.» rechazado por
_truncated_fact_word (volume es prefijo de clave ANIDADA volumePercent) y
_payload_fact_defect (efecto aplicado/verified perdido al proyectar como seen).
Ahora truncado mira valores de hojas, nunca claves anidadas; proyección conserva
effect:applied sólo con verified+succeeded+observed.applied verdaderos. Estado
final de audio se eleva igual que state, conserva60 y rechaza80.140pruebas dueñas
pass,1,29s. No se borran las protecciones de efecto no comprobado.

Mixto: turn.decide entrega clarify, pero App rechaza su pregunta y recae en
conversation; pierde objetivo y no puede entender «Al40%,please». App conserva
objetivo según PreserveObjective y vuelve a componer Clarification. No se
deducen operaciones nuevas ni se salta autorización. Prueba de integración
con fixture reproduce pregunta rechazada y comprueba contexto en próximo turno.
Primera compilación test falló por string?[]; corregido.51541 terminal1.
Segunda ejecución56497 TERMINAL0:1pass/0skip,6s.
Ruff y Fast41333 TERMINAL0:build0errores/0advertencias.
Python13211 TERMINAL0:1171pass+115subtests,9,71s,0skip.
Fuente llm.py e80013c982f275df6b06d59a55e439f05dbb1a62932bd1ba87717a7fc3c39fc9;
__main__.py d151ddab1174436dee4ed1950e81dff807501755b6ff09d4ab22913c5b7decfa.
KVq8 ahora es DEFAULT_KV_CACHE_TYPE; q4 sigue override diagnóstico admitido.
La repetición12 reparada71552 TERMINAL0: astra-clarification-repaired-qwen,
12publicados,76,17s,GPU3499,56MiB. Inglés60% YA responde correctamente. Mixto
conserva objetivo y lo combina, pero no aplica40%: pregunta por descuento/tiempo.
La traza demuestra otra causa: _volume_domain rechazaba la coma en
«volume, por favor», aunque aceptaba la misma continuación sin coma. Ahora
normaliza coma/punto y coma antes del modificador existente; todavía rechaza
«volumen, de ventas/datos/enciclopedia».1477pass test_effect_intent,40,51s.
64415 ACTIVO: astra-clarification-grounded-qwen, mismos12 con esa corrección;
no overrideKV, GGUF Qwen override aún. No iniciar segunda inferencia hasta recoger.
PRUEBAS_CONTINUIDAD_C03.md enlaza todos los literales antes/rechazos/perfilq4.

Próximo: recoger64415 y adjudicar12continuaciones; refrescar sellos/Fast finales.
Después fijar perfilq8 reproducible, panel restante/100/UI/averías/Full.
Anteriores29177/71986/32240terminal0. Familia.NET65172:7pass/0skip,45s.

## Resultado final del tramo

64415 terminó0:11/12publicados; dominio reparado pasó a plan, pero el plan
retenía el mismo fallo de pérdida de aclaración. Se retiraron las tres
implementaciones duplicadas y se reutiliza AddMindClarification en decisión,
plan y argumentos.3pruebas de frontera .NET pasan (17277,16s,0skip).
66482 terminó0: astra-clarification-unified-qwen12/12publicados,73,19s,
GPU3499,56MiB.80/60/40aplicados y leídos; restauración100comprobada. El script
c03-export-continuation.py comprueba los4efectos verified+succeeded+applied.
Fast7741 verde0errores/0advertencias; Python19363:1171pass+115subtests,8,80s.
Todos los procesos terminales. Registro Granite intacto, defaultKVq8 consolidado.
CHECKPOINT tiene siguiente paso: runtime registrado,100reservados/averías/UI/Full.
