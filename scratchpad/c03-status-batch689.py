"""Run fifty frozen survey requirements and shared status generalization variants."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-status-batch689-private'
assert psutil.virtual_memory().available >= 2700*2**20
private.mkdir(exist_ok=False)
registry = private.parent/'C03-survey-requirements336-private/requirements.jsonl'
with registry.open(encoding='utf-8-sig') as stream:
    requirements = {r['case_id']:r for r in map(json.loads,stream)}
groups = {
    'windows':['H0023','H0103','H0104','H0209','H0663'],
    'disk':['H0025','H0207','H0384','H0442','H0644'],
    'gpu':['H0026','H0087','H0114','H0194','H0370','H0625'],
    'memory':['H0111','H0156','H0162','H0342','H0532','H0539','H0655','H0508'],
    'battery':['H0037','H0144','H0359','H0379','H0665'],
    'cpu':['H0065','H0350'],
    'clock':['H0126','H0180','H0223','H0449','H0450','H0498','H0499','H0586','H0600','H0602','H0700','H0727'],
    'network':['H0127','H0433','H0732'],
    'processes':['H0364','H0650','H0675'],
    'audio':['H0383'],
}
assert len({c for ids in groups.values() for c in ids}) == 50
criteria = {
    'windows':'Fresh verified enumeration for a list/count query; fresh foreground observation for identity. Name the actual observed window(s), preserve count/scope and do not infer focus from display state. A truthful failure still does not fulfill an available requested read.',
    'disk':'Fresh system.status disk observation; answer requested free/used amount and requested drive (C when explicit). Distinguish bytes/GiB, free/used/total and avoid confusing RAM with storage.',
    'gpu':'Fresh system.status gpu_identity or gpu_usage matching the request. Identity includes the observed model; requested VRAM includes correct dedicated capacity. Usage is measured, never inferred from capacity or CPU.',
    'memory':'Fresh system.status memory or os_memory. Answer requested total/free/used physical RAM and Windows version when requested. Distinguish total, available, usage and VRAM; labels and units must agree with observations.',
    'battery':'Fresh system.status battery observation. Answer percentage or charging state as asked. If no battery is present, report that observed fact rather than inventing zero charge or a percentage.',
    'cpu':'Fresh system.status cpu measurement. Answer current measured CPU usage with units; the model name/core count alone does not answer usage.',
    'clock':'Fresh system.time for every turn, including follow-up. Answer local date or time as requested, preserve timezone and language, and do not reuse a stale conversation value. Greeting plus question still requires the clock answer.',
    'network':'Fresh wifi.status for connected WLAN identity/state or network.status for Internet connectivity, matching the query. Do not conflate link-up with verified Internet or invent SSID from opaque identifiers; missing requested identity remains a capability gap.',
    'processes':'Fresh system.process.list sorted by requested CPU/memory with requested top count. Name observed processes and explain measured values accurately; distinguish a process from aggregate app memory and do not invent rankings.',
    'audio':'Fresh audio.status. Answer current measured endpoint volume, preserving percentage and endpoint; do not change it.',
}
variants = {
    'windows': [('all-en','Please list the windows currently open.'),('focus-mixed','Baxy, ¿qué window tiene focus ahora?'),('focus-reference-es','¿Y ahora cuál está activa?')],
    'disk':[('free-en','How much free space is left on drive C?'),('used-es','Del disco C, dime cuánto espacio está ocupado.')],
    'gpu':[('identity-en','Which GPU does this PC have, and how much dedicated VRAM?'),('usage-es','¿Cuánta memoria de la GPU se está usando ahora?')],
    'memory':[('total-en','How much physical RAM does this computer have?'),('free-mixed','Baxy, dime la RAM free que queda ahora.'),('used-es','Ahora mismo, ¿cuánta RAM está en uso?')],
    'battery':[('charge-en','Is the battery charging right now?'),('level-es','Por favor, dime el porcentaje de batería restante.')],
    'cpu':[('usage-en','What percentage of the CPU is in use right now?'),('order-es','De la CPU, dime el porcentaje de uso actual.')],
    'clock':[('date-en','What is the current local date?'),('time-mixed','Hola Baxy, what time is it now?'),('date-reference-es','¿Y la fecha?')],
    'network':[('wifi-en','Which Wi-Fi network am I connected to?'),('internet-es','Comprueba si tengo conexión a Internet.')],
    'processes':[('top3-en','List the top 3 processes by RAM usage.'),('top2-es','Dime los dos procesos que más CPU consumen.')],
    'audio':[('status-en','What is the current system volume?'),('order-es','Del sonido del PC, dime el volumen actual.')],
}
panel = []
for group,ids in groups.items():
    for case_id in ids:
        row = requirements[case_id]
        assert row['expected_capability'] is True and row['verification_status'] == 'open'
        panel.append({'case_id':case_id,'group':group,'origin':'owner historical survey regression',
            'text':row['literal'],'owner_review':row['owner_review'],'criterion':criteria[group]})
    for suffix,text in variants[group]:
        panel.append({'case_id':group+'-'+suffix,'group':group,'origin':'assistant development generalization',
            'text':text,'supports':ids,'criterion':criteria[group]})
assert len(panel) == 73
(private/'panel.json').write_text(json.dumps(panel,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
plan = {'utc':datetime.now(timezone.utc).isoformat(),'owner_instruction':'Cubre en tandas de 50 cuberturas o de categorias enteras para hacerlo todo mas rapido',
    'survey_requirements':50,'development_variants':23,'groups':groups,
    'status':'registered_before_execution','survey_counts_before':{'covered':26,'open':716,'not_applicable':0},
    'requirements_sha256':hashlib.sha256(registry.read_bytes()).hexdigest(),
    'panel_sha256':hashlib.sha256((private/'panel.json').read_bytes()).hexdigest(),
    'criteria':criteria,'coverage_rule':'Each literal and every relevant variant is adjudicated against fresh typed observations and full requested scope. Batch size is not a pass count. Dynamic-value and name generalization still require evidence; no automatic group credit. Keep all failures for shared-cause repair.',
    'effect_scope':'Read-only PC status. Historical messages are data; no sending, changing apps, volume or user files. Hidden diagnostic profile; no UI/voice credit.',
    'inheritance':'686 validated/published;687 seven fresh reads but mixed descriptive subject still rejected;688 seventeen-case regression intact. Prior source/status/corpus evidence retained. This batch finds shared failures before further narrow edits.'}
(base/'STATUS_BATCH689_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
source = (root/'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source = source[source.index("source = (root / 'scratchpad/c03-private-product521.py')"):]
source = source.replace('astra-conversation-regression592','astra-status-batch689').replace('C03-conversation-regression592-private','C03-status-batch689-private').replace('C03-conversation-profile592','C03-status-profile689')
source = source.replace('Shared source590 product, base registered runtime, built-in diagnostics only. Twenty-one owner survey literals plus fourteen ES/EN/mixed development variants across identity, greeting, gratitude and small talk.',
    'Shared published source686 product, registered runtime, built-in diagnostics only. Fifty frozen positive survey requirements plus23 development variants across ten PC-status groups. Original literals and owner notes unchanged; fresh reads required. Batch diagnostic baseline, not automatic survey coverage.')
source = source.replace("'src/baxy_mind/cpu_prose_adapter.py',", "'src/baxy_mind/window_prose_facts.py', 'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',")
# More turns need a larger campaign watchdog, not a relaxed per-turn quality criterion.
source = source.replace("'wall_time_seconds': 240", "'wall_time_seconds': 900")
source = source.replace("exec(compile(source, __file__, 'exec'))", "source = source.replace('time.monotonic()-started>240', 'time.monotonic()-started>900')\nexec(compile(source, __file__, 'exec'))")
exec(compile(source,__file__,'exec'))
