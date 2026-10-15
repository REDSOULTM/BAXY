import re,sys
s=open(sys.argv[1],encoding='utf-8',errors='replace').read()
for block in s.split('=================== ')[1:]:
    name=block.split('\n')[0]
    finals=re.findall(r'^"(.+?)", "diagnostic"',block,re.M)
    lat=re.findall(r'"latency_ms":(\d+)',block)
    ends=re.findall(r'computer_use.end","detail":"([^"]+)"',block)
    mol=re.findall(r'^molestia: (.*)$',block,re.M)
    sys.stdout.buffer.write(f"{name} | {lat} | {ends[-1] if ends else '-'} | {' || '.join(f[:120] for f in finals)} | {mol[-1][:200] if mol else '-'}\n".encode('utf-8'))
# Agregado de molestia del lote: py -3.12 scripts/cu_live/molestia/molestia_sum.py <esta misma salida de batch.sh>
