"""Keep a compact current checkpoint; preserve the preceding checkpoint verbatim."""
from pathlib import Path
from datetime import datetime, timezone
import json

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
archive = base/'astra-private-projection344/PREVIOUS_CHECKPOINT.md'
if not archive.exists():
    archive.write_bytes((base/'CHECKPOINT.md').read_bytes())
checkpoint = '''# C03 — checkpoint344 — EN_CURSO — 2026-09-08

Goal completo activo, rama Goal-c03, HEAD2bf3d4c. Preservar WIP/main/evidencia;
sin agentes, commit ni push. No Full durante reparación. BAXY cerrado para uso
manual; encuesta1248/742 intacta y servidor101140 disponible. Instrucciones
directas consolidadas en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md; excluir órdenes
automáticas de otra tarea. La identidad y AGENTS siguen rigiendo.

## Hecho y evidencia

340: activación guiada por confirmación exacta, luego nuevo save protegido;
cancelar descarta la continuación. Dueñas1911pass/0skip y Fast18,77s.
342 acredita enable/save/recall pero publica que no sabe el nombre:2/7 completos,
una identidad parcial. Pérdida localizada en la proyección privada al compositor.
343/343b: dato requerido tipado supera ambos controles Python/App, conservando
vetos ajenos. Python1031pass/0skip; App217pass/0skip; Fast verde. Producto343b
2/2 controles sintéticos útiles,0silencio. No aceptación humana fresca/UI/voz.

344 reemplaza prosa fija de configuración/save/correct/forget/status/export por
hechos observed y transmite ahí los registros ya validados/redactados. Añade
pendingAction a confirmación inicial/reconciliación/recuperación privada. Owners:
MemoryOperationResponseProjection.cs y PrivateOperationNarration.cs. No fuente
Python nueva: su ruta observed→seen ya funciona. Mantiene schemas/secretos/replay.
Tests de prosa antiguos ahora exigen hechos y rechazan JSON como respuesta final.
Baseline9fail; focal9pass/0skip122ms; compositor Python85pass/0skip0,65s.

## En curso y siguiente acción

Dueñas .NET corriendo, handle67832, log astra-private-projection344/owners.log.
Recoger su terminación; resolver rojos sin relajar aserciones. Después Fast y
scratchpad/c03-product345.py, preparado desde342 con los mismos siete pedidos y
perfil/hook únicos. Leer cada mensaje y journal; no editar fuente durante producto.
El driver tiene pins de la nueva proyección y modelo registrado sin cambios.
344 PREREG/diagnóstico en astra-private-projection344 y PROYECCION_PRIVADA344_DISENO.md.

## Pendiente real

Identidad contextual105/107 y preguntas mientras se confirma siguen pendientes.
MemoryTurnSession.HandleConfirmationAsync/Invalid emite memory_confirm_or_cancel
sin pendingAction; inspección, aún no corregido. No afirmar memoria integrada.
Resto íntegro: ocho rutas,100humanos frescos (0certificados/0congelados;204 por
auditar335), averías/recuperación, UI escritorio/voz física/ASR/recursos conjuntos,
runtime/instalación, contratos C04–C09 sin ejecutar esos goals, Full final verde y
publicación fuera de main. Sin bloqueo externo ni porcentaje demostrado.
Histórico de recursos260:3516,66MiB GPU/4822,60MiB RAM; no mínimo ni conjunto voz.
Estado anterior íntegro: astra-private-projection344/PREVIOUS_CHECKPOINT.md.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    (base/name).write_text(checkpoint,encoding='utf-8')
state_path = base/'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='344 typed private projection implemented; focused9pass/Python85pass; .NET owners running67832.',
    continuation='Collect owners344, Fast, then native345 same seven development inputs; full C03 active.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('344 compact checkpoint saved; previous checkpoint preserved verbatim.')
