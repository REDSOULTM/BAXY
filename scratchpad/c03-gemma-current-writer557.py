"""Screen the18 actual shared-writer cases; closing resolved separately in555/556."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-gemma-current-writer554.py').read_text(encoding='utf-8')
source=source.replace('astra-gemma-current-writer554','astra-gemma-current-writer557').replace('C03-gemma-current-writer554-private','C03-gemma-current-writer557-private')
source=source.replace('assert len(cases)==20','assert len(cases)==18').replace('Twenty unmodified','Eighteen unmodified').replace('20 current Gemma','18 current Gemma')
source=source.replace('hardware observations, social closing and compound readings.','hardware observations and compound readings. Closing is deliberately absent:555/556 repaired its separate reference-resolution path;554 preflight exposed that distinction without running a model.')
exec(compile(source,__file__,'exec'))
