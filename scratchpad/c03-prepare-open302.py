from pathlib import Path
root=Path(__file__).resolve().parents[1]
text=(root/'scratchpad/c03-launch293.py').read_text(encoding='utf-8')
(root/'scratchpad/c03-launch302.py').write_text(text.replace('293','302'),encoding='utf-8')
