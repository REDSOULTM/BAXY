from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-analyze-voice135.py').read_text(encoding='utf-8')
source=source.replace('135','157').replace('134','148')
source=source.replace('Offline content and alignment comparison of physical candidate148 capture', 'Offline content around the observed interruption148: compare microphone and loopback; no assumption of its cause')
(root/'scratchpad/c03-analyze-voice157.py').write_text(source,encoding='utf-8')
print('Focused offline148 analyzer157 prepared.')
