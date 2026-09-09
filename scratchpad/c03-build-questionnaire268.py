"""Publish every recovered unique literal into a private owner review tool."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
source = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-real-user-pool-20260906'
out = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-owner-questionnaire-20260907'
out.mkdir(exist_ok=False)
pool = source/'unique_requests.jsonl'
pool_sha = hashlib.sha256(pool.read_bytes()).hexdigest()
manifest = json.loads((source/'MANIFEST.json').read_text(encoding='utf-8'))
assert pool_sha == manifest['poolSha256']
originals = [json.loads(line) for line in pool.read_text(encoding='utf-8').splitlines()]
integrity = {row['id']:row for row in (json.loads(line) for line in
    (source/'literal_integrity.jsonl').read_text(encoding='utf-8').splitlines())}
assert len(originals) == 742 and len({row['id'] for row in originals}) == 742
records = []
for index,row in enumerate(originals,1):
    literal = row['text_literal']
    assert hashlib.sha256(literal.encode('utf-8')).hexdigest() == row['id']
    records.append({'id':row['id'],'displayId':f'H{index:04d}','text':literal,
        'sources':row['occurrences'],'literalIntegrity':integrity.get(row['id']),
        'historicalMetadata':{key:value for key,value in row.items()
            if key not in ('id','text_literal','occurrences')}})
dataset = {'schema':'baxy.owner-questionnaire-data.v1','datasetId':pool_sha,
    'generatedAt':datetime.now(timezone.utc).isoformat(),'qa':False,
    'sourceManifest':manifest,'records':records,
    'judgmentMeaning':{'authorship':'Owner recalls sending this literal; does not attribute every occurrence.',
        'capability':'Owner expects BAXY to handle it correctly; not evidence of historical authorship.'}}
qa = out/'qa'
qa.mkdir()
qa_data = {'schema':dataset['schema'],'datasetId':'technical-qa-268','qa':True,
    'records':[{'id':'technical-qa-1','displayId':'PRUEBA-01',
        'text':'Prueba técnica. <script>window.unsafeQuestionnaire=true</script> ✓ ✕',
        'sources':[{'source':'Control técnico, no historial humano','timestamp':'2026-09-07'}]}]}
servers = []
for destination,data in ((out,dataset),(qa,qa_data)):
    (destination/'data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    shutil.copy2(root/'scratchpad/c03-questionnaire.html',destination/'index.html')
    shutil.copy2(root/'scratchpad/c03-questionnaire-server.py',destination/'server.py')
    chunks = []
    for row in data['records']:
        chunks.append(f"{row['displayId']} | {row['id']}\n{row['text']}\n")
        for occurrence in row['sources']:
            chunks.append(f"Origen: {occurrence.get('source','')} | {occurrence.get('timestamp','')} | {occurrence.get('source_location','')}\n")
        chunks.append('\n'+'-'*72+'\n\n')
    (destination/'messages.txt').write_text(''.join(chunks),encoding='utf-8')
    with (destination/'server.log').open('wb') as log:
        process = subprocess.Popen([sys.executable,str(destination/'server.py'),'--directory',str(destination)],
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic()+15
    while not (destination/'SERVER.json').exists():
        if process.poll() is not None:
            raise RuntimeError(f'Server failed: {destination}')
        if time.monotonic()>deadline:
            raise TimeoutError('Server observation timed out; inspect existing PID, do not restart blindly')
        time.sleep(.1)
    servers.append(json.loads((destination/'SERVER.json').read_text(encoding='utf-8')))
report = {'utc':datetime.now(timezone.utc).isoformat(),'count':len(records),'poolSha256':pool_sha,
    'sourceRecordReferences':sum(len(row['sources']) for row in records),
    'maxLiteralChars':max(len(row['text']) for row in records),
    'allLiteralsHashVerified':True,'prefilledOwnerJudgments':0,
    'privateDirectory':str(out),'servers':servers,
    'scope':'All 742 currently recovered unique literals, not a claim of exhaustive PC history.',
    'sourceHashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
        ['scratchpad/c03-questionnaire.html','scratchpad/c03-questionnaire-server.py','scratchpad/c03-build-questionnaire268.py']}}
evidence = root/'artifacts/comprobaciones/C03/astra-questionnaire268'
evidence.mkdir(exist_ok=False)
(evidence/'MANIFEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'count':len(records),'urls':[server['url'] for server in servers],
    'pids':[server['pid'] for server in servers],'directory':str(out),'maxLiteralChars':report['maxLiteralChars']}))
