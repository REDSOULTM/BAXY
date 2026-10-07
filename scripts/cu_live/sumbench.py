import re,sys
s=open(sys.argv[1],encoding='utf-8',errors='replace').read()
for block in s.split('=================== ')[1:]:
    name=block.split('\n')[0]
    finals=re.findall(r'^"(.+?)", "diagnostic"',block,re.M)
    lat=re.findall(r'"latency_ms":(\d+)',block)
    ends=re.findall(r'computer_use.end","detail":"([^"]+)"',block)
    sys.stdout.buffer.write(f"{name} | {lat} | {ends[-1] if ends else '-'} | {' || '.join(f[:120] for f in finals)}\n".encode('utf-8'))
