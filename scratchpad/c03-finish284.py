from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
report = '''# C03 — recuperación de sesión y conservación de cuenta279–284

Estado EN_CURSO. No aceptación ni promoción de modelo.

279 comparó schemas tipados reales con tools vacías sobre siete controles de278.
5/7 criterios semánticos: las tres aperturas del dueño se recuperan, pero win07
continúa app.installed y cmp01 sólo devuelve música, omitiendo app.open. No adoptar.
PREREG/RESULT en astra-schema279; fuente sin cambios. No truncamiento (3240–3612
tokens de prompt, contexto4096). Herencia y documentación Qwen consignadas allí.

280 guardó un dump Heap privado del proceso84328 con dotnet-dump10.0.731102,
herramienta oficial de diagnóstico, sin subir contenido. 281 detectó que la
presentación textual SOS perdía caracteres no ASCII: falló la comprobación de
longitud, por lo que no se aceptó esa extracción. 282 siguió la colección real
MainWindowViewModel.Messages, lista de121 elementos, y extrajo bytes UTF16LE.
Resultado exacto:63 mensajes del dueño,58 de BAXY; orden, longitud y horas
comprobados. No equivale a nueva captura de píxeles ni a100 turnos frescos.

Transcripción completa privada:
C:/Users/usuario/AppData/Local/BAXY/C03-owner264-heap280/TRANSCRIPT282.md
JSON SHA256 9658a77505564ec1384e58aba91ed75d03b078f865182f94b6ecc3b0ee839ef6.
No añadir dump ni transcripción completa a Git. Evidencia pública mínima:
astra-heap280/COLLECT.json y astra-transcript282/RESULT.json.
Ya se cumplió preservar conversación antes de reiniciar instancia264.

283: «quien soy» → «Hola, soy BAXY.» aunque Core entregó system.identity
verificado con userName. Comparación de una obligación dinámica de conservación
del dato, mismo primer payload y modelo local. Nueva respuesta:
«Tu nombre de usuario en el sistema es usuario.» No afirma guardar nombre personal.

284 incorpora esa obligación en llm._payload_fact_defect, reutilizando missing_name
y reintento existentes. No texto visible fijo, constante de usuario ni blacklist
de frases. Controles de nombre distinto, acentos, mayúsculas, nombres compuestos,
ausencia de dato y reintento real de compose_user_message.
Las primeras versiones de controles tenían errores de idioma y usaban
compose_visible_defect, que no es dueño del guard de payload. Se corrigieron al
límite real _compose_situation_payload→_payload_fact_defect; el test de composición
completa se conservó. Todos los logs fallidos permanecen para trazabilidad.
Control previo, guard antiguo aislado en proceso:5fail8pass30deselected0,41s.
Fuente actual: pytest tests/test_compose_contract.py tests/test_llm_transport.py
tests/test_turn_policy.py -q --tb=short →1012pass0skip5,20s. Ruff verde.
Repetición nativa con fuente adoptada, sin monkeypatch: misma respuesta correcta,
primer payload idéntico a283. astra-account284/NATIVE_RESULT.json.

Límites: no corrige selección system.identity ni memoria personal. Persisten
negaciones falsas de capacidades, conversación contextual, compuestos, resultados
ausentes y veracidad del resto de sesión. Fast integrado266/267/284 pendiente;
últimoFast262. No Full durante reparación. Cuestionario742 sigue disponible,
respuestas del dueño intocadas. Campaña final, voz, recursos, instalación,
continuidad y publicación fuera main pendientes.
'''
(out / 'SESION_Y_CUENTA279_284.md').write_text(report, encoding='utf-8')
checkpoint = '''# C03 — checkpoint284 — EN_CURSO

Última tanda SESION_Y_CUENTA279_284.md. 279 schemas reales:5/7, no adoptar.
280–282 RECUPERADA conversación completa de UI264:121 elementos,63usuario58BAXY,
bytes UTF16LE exactos con tiempos, guardados privados en
%LOCALAPPDATA%/BAXY/C03-owner264-heap280/TRANSCRIPT282.json y .md.
281 presentación SOS con pérdida Unicode rechazada, no usar. No subir dump/raw.
Ya se puede gestionar/reiniciar264: condición de preservar memoria cumplida.

284 fuente llm._payload_fact_defect conserva seen.userName dinámico.
Owner t56: antes Hola, soy BAXY; después Tu nombre de usuario en el sistema es
usuario. Nativo real adoptado sin monkeypatch, mismo primer payload283.
Tres suites1012pass0skip5,20s; ruff verde. Baseline antiguo5fail8pass reproduce.
No corrige memoria personal ni selección identity. Fast266/267/284 aún pendiente,
últimoFast262. No Full durante reparación.

SIGUIENTE: reparar conversación falsa fuera de alcance (París índices1–10),
partiendo de payload/primera transformación errónea y herencia. Después atender
memoria, contexto/afirmaciones falsas, compuestos y respuestas ausentes del owner.
No otra heurística de prioridad Steam:274–279rechazadas (SELECCION274_278.md).
Modelo actual Qwen3.5 override, no promoción; backend89232/57485 compartido,
comprobar slots antes de ensayos nativos. App84328 oculta con fuente vieja.

Cuestionario742 http://127.0.0.1:63179/ PID101140 SIN cierre automático.
%LOCALAPPDATA%/BAXY/C03-owner-questionnaire-20260907/answers.json pertenece al
dueño. No borrar/sobrescribir/rellenar/congelar mientras revisa. Autoría y capacidad
independientes. Tres ingleses admitidos previamente siguen vigentes.

Goal-c03/HEAD2bf3d4c, preservar WIP/main. Registro13b971… no promovido.
Recursos2603516,66MiBGPU/4822,60MiBRAM con captura/AEC/Piper, sin ASR humano;
wake sin certificar. Ocho rutas,100/100humanos frescos sin congelar,
averías/recuperación, UI/voz/ASR/recursos finales, runtime/instalación,
continuidadC04–C09, Full y publicación fuera main pendientes. Sin bloqueo externo.
'''
for name in ('CHECKPOINT.md','HANDOFF.md'):
    (out / name).write_text(checkpoint, encoding='utf-8')
path = out / 'RELEVO_ACTIVO.json'
record = json.loads(path.read_text(encoding='utf-8'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='284: full owner UI recovered privately; account preservation adopted,1012 tests green and actual native verified.',
    continuation='Investigate first erroneous Paris conversation boundary; integrated Fast266/267/284 pending. Preserve questionnaire.')
record['userOwnedInstance']['instruction'] = 'Owner authorized review/control; complete conversation preserved in private TRANSCRIPT282. Can manage controlled restart now.'
path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
pins = {}
for name in ('src/baxy_mind/llm.py','tests/test_compose_contract.py','artifacts/comprobaciones/C03/SESION_Y_CUENTA279_284.md'):
    pins[name] = hashlib.sha256((root/name).read_bytes()).hexdigest()
(out/'TRAMO279_284_PINS.json').write_text(json.dumps(pins, indent=2)+'\n',encoding='utf-8')
print('Checkpoint284 written; private data and questionnaire unchanged.')
