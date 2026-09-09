from pathlib import Path
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
content = '''# C03 — checkpoint296 — EN_CURSO

Fuente adoptada284 sin cambios posteriores. 1012 pass, 0 skips, 5,20s;
ruff y Fast287 integrado VERDE (build4,45s,0warn/error). No Full de reparación.

292: comparación selector AUTO con los mismos 18 payloads289/290, modelo
registrado2507:17/18 correctos; window.application.status confunde window.active.
París termina sin efecto en replay, pero UI293 con historial nuevo pide aclarar
inútilmente tras web.search→domain_grounding→domain_confirmation. Segunda prueba
UI293 «quien soy» muestra «Soy usuario, en el dominio REDNOTE.»: preservar el nombre
284 es necesario pero NO garantiza atribución correcta. Qwen3.5 UI288 sí decía
«Tu nombre de usuario en el sistema es usuario.». No declarar identidad resuelta.
294: restaurar schemas completos2507 empeora a14/18; DESCARTADO, sin adopción.
295: proyectar AskToSave como hecho legible sigue preguntando innecesariamente;
DESCARTADO.296: chat real sin persistencia genera «Hola Emmanuel, ¿cómo estás? 😎»
para «me llamo emmanuel, dime hola emmanuel», pero guard de publicación rechaza
primer intento y retry válido. SIGUIENTE: identificar predicado exacto con replay
de RESULT296; conservar controles válidos/inválidos. No adivinar ni barrer prompts.
Parser AskToSave aún intercepta la petición mixta antes de conversación: reparar
esa frontera requiere preservar consentimiento; memory.save es Public LowReversible.

Evidencia: astra-selector-model292, astra-ui293, astra-schemas294,
astra-memory295 y astra-memory296. Scripts homónimos en scratchpad.292 servidor
standalone terminado; UI288 detenida tras snapshot privado completo292. No nuevas
escrituras de producto ni promoción de modelo292–296. Último informe anterior:
UI_Y_TERMINACION285_291.md; resultados nuevos requieren informe consolidado.

UI293 ABI real ABI actual abierta, sin temporizador: App97436 creado1788828033.4354932,
launcher40020, backend71708 creado1788828041.3328712, puerto63490. Modelo registrado
2507, fuente284; logs privados %LOCALAPPDATA%/BAXY/C03-ui293-private. No usar nativo
con /slots activo. Controles UI293 son del agente, no humanos frescos.
Sesión humana264 íntegra:121 mensajes(63dueño58BAXY), TRANSCRIPT282.json/.md en
%LOCALAPPDATA%/BAXY/C03-owner264-heap280; no subir heap ni texto completo.

Cuestionario742 http://127.0.0.1:63179/ PID101140 abierto sin cierre automático.
answers.json del dueño en C03-owner-questionnaire-20260907: no borrar, sobrescribir,
rellenar ni congelar. Autoría y capacidad separadas; tres ingleses admitidos vigentes.

Goal-c03/HEAD2bf3d4c, preservar WIP/main. Recursos260:3516,66MiBGPU/4822,60MiBRAM
con captura/AEC/Piper sin ASRhumano; no medición integral nueva293. Wake sin certificar.
Pendientes: ocho rutas útiles,100/100humanos frescos sin congelar, averías/recuperación,
UI/voz/ASR/recursos finales, runtime/instalación, continuidadC04–C09, Full y publicación
fuera main. Sin bloqueo externo; objetivo completo sigue activo.
'''
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    (base / name).write_text(content, encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
data = json.loads(p.read_text(encoding='utf-8'))
data.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='296: registered selector292 17/18; actual UI293 clarification and identity-role defects; schemas294 and memory projection295 rejected; chat296 valid raw greeting rejected.',
    continuation='Replay296 to identify exact publication predicate; preserve memory consent and owner questionnaire. Whole C03 active.')
data['userOwnedInstance'].update(pid=97436, createTime=1788828033.4354932,
    launcher=40020, privateLogs=r'C:\Users\usuario\AppData\Local\BAXY\C03-ui293-private',
    instruction='Keep UI293 open; distinguish agent controls from owner264 session. Backend71708 port63490 registered2507.')
p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
