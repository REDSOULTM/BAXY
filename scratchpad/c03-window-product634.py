"""Registered product: named application window reads and scope controls."""
from pathlib import Path
import json
import os
root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-window-product634-private'
private.mkdir(exist_ok=False)
specs=[
 ('H0040','hay alguna ventana de steam abierta','window.application.status','Steam'),
 ('H0040-en','Is Spotify open?','window.application.status','Spotify'),
 ('window-name-es','¿Está Bloc de notas abierto?','window.application.status','Bloc de notas'),
 ('window-closed-en','Please check whether Paint is closed','window.application.status','Paint'),
 ('window-name-en','Is Google Chrome open?','window.application.status','Google Chrome'),
 ('window-order-es','¿Está abierta la aplicación Spotify?','window.application.status','Spotify'),
 ('window-order-en','Are any windows of Steam open?','window.application.status','Steam'),
 ('window-courtesy-es','Baxy, por favor: comprueba si Paint está abierto','window.application.status','Paint'),
 ('focus-es','¿Qué ventana está activa?','window.active',None),
 ('focus-en','Which window has focus?','window.active',None),
 ('missing-volume-control','Pon el volumen a...',None,None),
 ('no-window-control','No abras ninguna ventana.',None,None),
]
panel=[]
for case,text,operation,name in specs:
    criterion=(
        'Read the specific application window status. Final must agree with verified installed/visibleWindowCount fields, preserve the name and language, and never infer background process absence from no visible windows.'
        if name else 'For a focus question read window.active and describe only the foreground observation; for missing volume ask its value; for the negative constraint acknowledge without dispatch. No write operation.'
    )
    panel.append({'case_id':case,'text':text,'operation':operation,'name':name,
        'origin':'owner historical regression' if case.startswith('H0040') else 'assistant development generalization/control',
        'criterion':criterion})
(private/'panel.json').write_text(json.dumps(panel,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source=source[source.index("source = (root / 'scratchpad/c03-private-product521.py')"):]
source=source.replace('astra-conversation-regression592','astra-window-product634').replace('C03-conversation-regression592-private','C03-window-product634-private').replace('C03-conversation-profile592','C03-window-profile634')
source=source.replace('Shared source590 product, base registered runtime, built-in diagnostics only. Twenty-one owner survey literals plus fourteen ES/EN/mixed development variants across identity, greeting, gratitude and small talk.',
 'Shared source633 product, base registered runtime, built-in diagnostics only. Eight named application queries with ES/EN/order/name variation, two foreground controls, missing volume and negative constraint.')
source=source.replace('Generalization variants support only their declared group.',
 'Require the specific typed observation in the panel, not merely plausible prose. No write operation authorized. Visible windows do not prove background process liveness.')
source=source.replace("'src/baxy_mind/cpu_prose_adapter.py',", "'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',")
exec(compile(source,__file__,'exec'))
