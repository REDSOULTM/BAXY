import json, os, sys, time
from pathlib import Path

def summary(root: Path):
    files=bytes_=dirs=0
    errors=0
    newest=None
    newest_rel=None
    t0=time.perf_counter()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirs += 1
        for name in filenames:
            p=os.path.join(dirpath,name)
            try:
                st=os.lstat(p)
            except OSError:
                errors += 1
                continue
            files += 1
            bytes_ += st.st_size
            if newest is None or st.st_mtime>newest:
                newest=st.st_mtime
                newest_rel=os.path.relpath(p, root)
    return {'files':files,'dirs':dirs,'bytes':bytes_,'errors':errors,'newest_rel':newest_rel,'elapsed_s':round(time.perf_counter()-t0,3)}

subs = []
pairs = [
    r'D:\Perfil\Escritorio\ETC\Programacion\Probando Gemma 4\models',
    r'D:\Perfil\Escritorio\ETC\Programacion\Probando Gemma 4\data',
    r'D:\Perfil\Escritorio\ETC\Programacion\Probando Gemma 4\gemma4_agent',
    r'D:\Perfil\Escritorio\ETC\Programacion\Probando Gemma 4\dataset_finetune',
    r'D:\Perfil\Escritorio\ETC\Programacion\FunctionGemma\model',
    r'D:\Perfil\Escritorio\ETC\Programacion\FunctionGemma\finetune_llm',
    r'D:\Perfil\Escritorio\ETC\Programacion\FunctionGemma\router',
    r'D:\Perfil\Escritorio\ETC\Programacion\FunctionGemma\speech_model',
    r'D:\Perfil\Escritorio\ETC\Programacion\BAXY\legacy\models\artifacts',
    r'D:\BAXYRuntime\datasets',
    r'D:\BAXYRuntime\assets',
]
for p in pairs:
    r=Path(p)
    rec={'path':p,'exists':r.exists()}
    if r.exists():
        rec.update(summary(r))
        rec['child_names']=[x.name for x in list(r.iterdir())[:40]]
    subs.append(rec)
    print(p, rec.get('exists'), rec.get('files'), rec.get('bytes'), rec.get('child_names','')[:8], flush=True)
Path(sys.argv[1]).write_text(json.dumps(subs, indent=2), encoding='utf-8')
