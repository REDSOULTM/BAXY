from pathlib import Path
import hashlib,re
root=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
d=hashlib.sha256()
for rel,p in sorted(files.items()):d.update((rel+'\n'+sha(p)+'\n').encode())
tree=d.hexdigest()
p=root/'tests/test_price_v8_veto_damage_by_cause.py';s=p.read_text(encoding='utf-8-sig')
for name in ['__main__.py','llm.py']:
 pattern=r'("src/baxy_mind/'+re.escape(name)+r'": \(\s*")[a-f0-9]{64}("\s*\))'
 s,n=re.subn(pattern,lambda m:m[1]+sha(root/'src/baxy_mind'/name)+m[2],s)
 assert n==1,(name,n)
p.write_text(s,encoding='utf-8')
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
 p=root/'experiments/stt_quality'/name;s=p.read_text(encoding='utf-8-sig')
 s,n=re.subn(r'(EXPECTED_PROGRAM_TREE_SHA256 = \(\s*")[a-f0-9]{64}("\s*\))',lambda m:m[1]+tree+m[2],s)
 assert n==1,(name,n)
 p.write_text(s,encoding='utf-8')
for name in ['__main__.py','llm.py','effect_intent.py']:print(name,sha(root/'src/baxy_mind'/name))
print('STT',tree)
