import re,sys,os
# Markdown rows «| caso | orden | resultado | misión | respuesta | final |» from a batch output; the verdict column is
# filled from argv[2] (a file «caso<TAB>veredicto» written by the lead after checking each case).
out=open(sys.argv[1],encoding='utf-8',errors='replace').read()
verdicts={}
if len(sys.argv)>2 and os.path.exists(sys.argv[2]):
    for line in open(sys.argv[2],encoding='utf-8'):
        if '\t' in line:
            k,v=line.rstrip('\n').split('\t',1); verdicts[k]=v
base=os.path.dirname(sys.argv[1])
rows=[]
for block in out.split('=================== ')[1:]:
    name=block.split('\n')[0].strip()
    turns=[t.strip() for t in open(os.path.join(base,name+'.turns'),encoding='utf-8') if t.strip()]
    finals=[f.replace('\\"','"') for f in re.findall(r'^"(.+?)", "diagnostic"',block,re.M)]
    lat=re.findall(r'"latency_ms":(\d+)',block)
    ends=re.findall(r'computer_use.end","detail":"reached.true.steps.\d+.ms.(\d+)',block)
    mission=f"{int(ends[-1])/1000:.1f} s" if ends else "—"
    resp=" / ".join(f"{int(x)/1000:.1f}" for x in lat)+" s" if lat else "—"
    fin=" / ".join(f[:140] for f in finals).replace('|','/')
    rows.append(f"| {name} | {' / '.join(turns)} | {verdicts.get(name,'?')} | {mission} | {resp} | {fin} |")
sys.stdout.buffer.write(("\n".join(rows)+"\n").encode('utf-8'))
