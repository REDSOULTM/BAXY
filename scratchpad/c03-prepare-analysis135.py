from pathlib import Path
s = Path('scratchpad/c03-analyze-voice126.py').read_text(encoding='utf-8')
s = s.replace('astra-analysis126', 'astra-analysis135').replace('analysis126.json', 'analysis135.json')
s = s.replace('[123, 125]', '[134]').replace('["off-before", "direct", "off-after"]', '["direct"]')
s = s.replace('existing physical123/125 captures', 'physical candidate134 capture')
with Path('scratchpad/c03-analyze-voice135.py').open('x', encoding='utf-8') as f:
    f.write(s)
