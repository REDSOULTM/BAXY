"""Shared product with scoped adapter override, not registered promotion."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-cpu-actor-product582.py').read_text(encoding='utf-8')
for old, new in [('astra-cpu-actor-product582', 'astra-scoped-lora-product589'), ('C03-cpu-actor-product582-private', 'C03-scoped-lora-product589-private'), ('C03-cpu-actor-profile582', 'C03-scoped-lora-profile589'), ('c03-owner582-hook', 'c03-owner589-hook')]:
    source = source.replace(old, new)
source = source.replace('source581', 'source584 with experimental scoped CPU adapter pilot4, not registered promotion')
needle = "source = (root / 'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')"
insertion = "(hook / 'sitecustomize.py').write_text((hook / 'sitecustomize.py').read_text(encoding='utf-8') + '\\n' + (root / 'scratchpad/c03-cpu-lora-hook589.py').read_text(encoding='utf-8'), encoding='utf-8', newline='\\n')\n" + needle
# The outer582 wrapper builds568; append the adapter hook after568 creates its observer.
source = source.replace("exec(compile(source, __file__, 'exec'))", f"source = source.replace({needle!r}, {insertion!r})\nexec(compile(source, __file__, 'exec'))")
exec(compile(source, __file__, 'exec'))
