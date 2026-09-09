"""Shared-product survey generalization, read-only and explicit no-action controls."""
from pathlib import Path
import json
import os
import psutil

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-survey-readonly568-private'
assert psutil.virtual_memory().available / 2**20 > 3000
private.mkdir(exist_ok=False)
specs = [
    ('H0037', ['está cargando la batería', 'Is the battery charging right now?', '¿La batería se está cargando o descargando?']),
    ('H0063', ['mostrame la batería', 'How much battery do I have left?', '¿Qué porcentaje de batería queda?']),
    ('H0073', ['mostrame el volumen', 'What is the volume level, and is it muted?', '¿Está silenciado el sonido y en cuánto está el volumen?']),
    ('H0080', ['funciona mi internet', 'Is this computer connected to the internet?', '¿Tengo conexión a internet ahora?']),
    ('H0057', ["don't open chrome", 'No abras Firefox.', 'Opera no lo abras ahora.']),
]
cases = [{'case_id': case_id, 'origin': 'owner historical survey' if index == 0 else 'assistant development variant', 'text': text}
         for case_id, variants in specs for index, text in enumerate(variants)]
(private / 'panel.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
hook = root / 'scratchpad/c03-owner568-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text((root / 'scratchpad/c03-owner521-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-private-product521-private', 'C03-survey-readonly568-private'), encoding='utf-8', newline='\n')
source = (root / 'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
for old, new in [('astra-private-product521', 'astra-survey-readonly568'), ('C03-private-product521-private', 'C03-survey-readonly568-private'), ('C03-private-profile521', 'C03-readonly-profile568'), ('c03-owner521-hook', 'c03-owner568-hook')]:
    source = source.replace(old, new)
start = source.index('cases = '); end = source.index('\n\ncommands =', start)
source = source[:start] + "cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]" + source[end:]
start = source.index('prereg = {'); end = source.index("(out/'PREREG.json').write_text", start)
source = source[:start] + '''prereg={
 'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Shared product, registered Qwen2507/b9980 and source555. Five survey requirements each with literal and two new variants: charging, battery percentage, volume/mute, internet connectivity and prohibitions naming three browsers across ES/EN. Verify every final against actual native observations; prohibited openings must yield no effect. Isolated profile, no manual desktop/voice credit.',
 'authorization':'AUTORIZACION_DUENO_536.md; current owner-approved historical inputs and explicit new development variants. No outgoing user content, private memory mutations or app launches requested.',
 'criteria':'Correct observation scope, values/state and subject; no invented success or permanent limitations. Negation preserves app and does not execute the action. Publication alone is not coverage. Charging/current connectivity are observed snapshots, not physical unplug/restore tests.',
 'manifest_sha256':sha(manifest),'panel_sha256':sha(private/'panel.json'),
 'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/llm.py','src/baxy_mind/__main__.py','src/baxy_mind/effect_intent.py']},
 'private':str(private),'case_count':len(cases),
 'resource_limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'wall_time_seconds':240}}
''' + source[end:]
exec(compile(source, __file__, 'exec'))
