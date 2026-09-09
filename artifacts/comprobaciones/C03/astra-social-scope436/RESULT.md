# 436 — contexto acotado sólo para presentaciones sociales completas

_prepare_turn_result envía historia vacía a chat únicamente para una decisión
explícita completa cuyo resultado es social. La historia original no se modifica;
recuerdos, seguimientos, compuestos, aclaraciones pendientes y conversaciones
clasificadas por el modelo conservan su recorrido. Se reutiliza el principio de
alcance de las definiciones nuevas; no cambia ningún prompt, modelo ni sampler.

435 aisló esta diferencia: cuatro presentaciones1/4→4/4, siete actos sociales
4/7→7/7 semánticos, tres controles sin transformación idénticos. No acreditó
idioma EN de producto porque mantuvo el sistema ES del payload para comparar.

- Baseline focal:3fail/0pass/0skips,2,72s.
- Focal con seguimientos/contexto:26pass/0skips,0,94s.
- Owners turn_policy/request_reading/compose_contract/llm_transport:
  1397pass/0skips,6,94s.
- Fast entero verde; build4,19s,0 advertencias y0 errores.

437 repetirá el mismo recorrido434. T7 sigue pendiente; no se considera C03
cerrado y no se consume aceptación humana fresca. No Full durante reparación.
