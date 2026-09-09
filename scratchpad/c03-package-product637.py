"""Same634 read-only panel after the first packaged identity repair636."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-window-product634.py').read_text(encoding='utf-8')
source=source.replace('window-product634','package-product637').replace('window-profile634','package-profile637')
source=source.replace('Shared source633 product','Shared source636 product')
source=source.replace("'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',", "'src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs', 'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',")
exec(compile(source,__file__,'exec'))
