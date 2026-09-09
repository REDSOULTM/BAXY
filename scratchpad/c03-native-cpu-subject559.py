"""Explain the measured CPU subject without changing any observed field."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-cpu-owner558.py').read_text(encoding='utf-8')
source=source.replace('astra-native-cpu-owner558','astra-native-cpu-subject559').replace('C03-native-cpu-owner558-private','C03-native-cpu-subject559-private')
start=source.index('def treatment(payload):')
end=source.index("write(out/'PREREG.json'",start)
source=source[:start]+'''def treatment(payload):
    payload['messages'][0]['content']+='\\\\nEl porcentaje de uso de CPU mide todo el equipo, no el consumo de BAXY. Al dar esa medida, conserva a quién pertenece.'
''' +source[end:]
source=source.replace('Only rename the CPU usagePercent evidence field to wholeComputerUsagePercent, keeping its numeric value, logical count, model, failures, request and prompts unchanged.', 'Add only one system instruction stating the CPU percentage measures the whole computer rather than BAXY consumption. All observed fields and values remain unchanged; no rename558.')
source=source.replace('This tests ownership semantics rather than another global voice/prompt rewrite.', '558 field rename failed Spanish ownership and changed an English logical-count response. Test the explicit measurement semantics for this bounded status responsibility; no global prose rewrite. Stop if this second ownership attempt fails.')
exec(compile(source,__file__,'exec'))
