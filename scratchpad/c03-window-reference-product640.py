"""Current638: packaged positive name, coreference and count generalization."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
prefix=(root/'scratchpad/c03-enumeration-product639.py').read_text(encoding='utf-8')
prefix=prefix[:prefix.index("source=(root/'scratchpad/c03-package-product637.py')")]
prefix=prefix.replace('enumeration-product639','window-reference-product640')
exec(compile(prefix,__file__,'exec'))
source=(root/'scratchpad/c03-window-product634.py').read_text(encoding='utf-8')
source=source.replace('window-product634','window-reference-product640').replace('window-profile634','window-reference-profile640')
source=source.replace('Shared source633 product','Shared source638 product')
source=source.replace('Eight named application queries with ES/EN/order/name variation, two foreground controls, missing volume and negative constraint.',
 'Same12window controls plus8declared packaged app, reference, alias and cardinality variants. Reference targets follow the exact previous question: WhatsApp then Spotify then Steam. Quantities must agree with real observations. No communication authorized.')
source=source.replace('private.mkdir(exist_ok=False)','assert private.is_dir()')
source=source.replace('panel=[]', '''specs += [
 ('package-positive-es','¿Está abierta la aplicación WhatsApp?','window.application.status','WhatsApp'),
 ('package-positive-en','Is WhatsApp open?','window.application.status','WhatsApp'),
 ('reference-new-name-en','And Spotify?','window.application.status','Spotify'),
 ('reference-pronoun-en','Is it open now?','window.application.status','Spotify'),
 ('reference-new-name-es','¿Y Steam?','window.application.status','Steam'),
 ('reference-pronoun-es','¿Esa aplicación tiene alguna ventana abierta?','window.application.status','Steam'),
 ('count-es','¿Cuántas ventanas de Steam están abiertas?','window.application.status','Steam'),
 ('count-en','How many windows of Steam are open?','window.application.status','Steam'),
]
panel=[]''')
source=source.replace("'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',", "'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs', 'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',")
try:
    exec(compile(source,__file__,'exec'))
finally:
    save('windows-after.json')
