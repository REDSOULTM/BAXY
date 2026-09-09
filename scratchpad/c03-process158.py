from pathlib import Path
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-audio158'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio158-private'
pid=json.loads((out/'PROCESS.json').read_text(encoding='utf-8'))['app']
names=['BAXY_VOICE_WAKE_MANIFEST','BAXY_VOICE_WAKE_CASCADE_MANIFEST','BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED',
    'BAXY_VOICE_WAKE_ON_START','BAXY_MIND_LLM_GGUF','BAXY_ASSET_DESCRIPTOR','BAXY_DATA_DIR','PYTHONPATH']
rows=[]
try:
    app=psutil.Process(pid)
    for proc in [app,*app.children(recursive=True)]:
        if proc.name().lower() not in ['baxy.exe','python.exe','llama-server.exe','piper.exe']:
            continue
        row={'pid':proc.pid,'name':proc.name(),'created':proc.create_time(),'cmdline':proc.cmdline()}
        try:
            env=proc.environ()
            row['selectedEnvironment']={k:env[k] for k in names if k in env}
        except psutil.Error as error:
            row['environmentError']=type(error).__name__
        rows.append(row)
finally:
    (private/'process158.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (out/'STOP_APP').touch(exist_ok=False)
print(json.dumps(rows,indent=2))
