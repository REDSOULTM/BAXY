"""Test decimal GB after552 binary values were mislabeled as decimal units."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-native-quantities552.py').read_text(encoding='utf-8')
source=source.replace('astra-native-quantities552','astra-native-quantities553').replace('C03-native-quantities552-private','C03-native-quantities553-private')
source=source.replace("'GiB'","'GB'").replace('derived-GiB','derived-GB').replace('item/(2**30)','item/(10**9)').replace('derived GiB siblings','derived decimal GB siblings')
source=source.replace('Test whether explicit physical quantities resolve numeric claims before changing source.', '552 computed binary quantities were routinely narrated with decimal GB labels; rejected. This second comparison computes decimal GB directly, isolating units from the same observed byte values. Stop this representation line if factual regressions remain.')
exec(compile(source,__file__,'exec'))
