"""Read-only filename inventory authorized by owner; never open/upload audio."""
from pathlib import Path
from datetime import datetime, timezone
import collections
import json
import os
import time

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-find-audio196'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-find-audio196-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
audio_extensions = {'.wav','.flac','.mp3','.m4a','.ogg','.opus','.webm','.wma','.aac','.aiff','.aif','.pcm'}
project = Path('D:/Perfil/Escritorio/ETC/Programacion')
excluded = [root, Path('C:/Windows'), Path('C:/$Recycle.Bin'), Path('D:/$Recycle.Bin'),
            Path('C:/System Volume Information'), Path('D:/System Volume Information')]
skip_names = {'.git','node_modules','__pycache__','WinSxS'}

def key(p): return os.path.normcase(os.path.abspath(p))
excluded_keys = {key(p) for p in excluded}
priority = [project / name for name in ['Probando Gemma 4','BAXY','Carter OS AI','FunctionGemma']]
priority_keys = {key(p) for p in priority}
started = time.monotonic()
files_seen = directories = 0
counts = collections.Counter()
errors = []
skips = collections.Counter()
stack = [('C:/', False), ('D:/', False)] + [(str(p), True) for p in reversed(priority)]
def save(p, value): p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out / 'PREREG.json', {'utc':datetime.now(timezone.utc).isoformat(),
    'authorization':'Owner explicitly permits searching previous projects or whole PC for voice recordings.',
    'roots':['C:/','D:/'], 'priorityProjects':[str(p) for p in priority],
    'excluded':[str(p) for p in excluded], 'prunedNames':sorted(skip_names),
    'extensions':sorted(audio_extensions), 'method':'Names and stat metadata only; no content reads or external transmission. Skip junctions/reparse points and this current evidence tree. Current private C03 captures omitted as already known. 300s bounded pass, preserve frontier if incomplete.',
    'privacy':'Detailed paths remain in LOCALAPPDATA/BAXY/C03-find-audio196-private.'})
with (private/'files.jsonl').open('w',encoding='utf-8') as log:
    while stack and time.monotonic()-started < 300:
        dirname, is_priority = stack.pop()
        if key(dirname) in excluded_keys:
            skips['excluded_root'] += 1; continue
        if not is_priority and key(dirname) in priority_keys:
            continue
        try:
            with os.scandir(dirname) as entries:
                directories += 1
                for entry in entries:
                    try:
                        if entry.is_symlink() or os.path.isjunction(entry.path):
                            skips['link_or_junction'] += 1; continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name in skip_names or (entry.name.startswith('C03-') and key(dirname)==key(Path(os.environ['LOCALAPPDATA'])/'BAXY')):
                                skips['known_cache_or_current_capture'] += 1
                            else:
                                stack.append((entry.path,is_priority))
                        elif entry.is_file(follow_symlinks=False):
                            files_seen += 1
                            ext = Path(entry.name).suffix.lower()
                            if ext in audio_extensions:
                                info = entry.stat(follow_symlinks=False)
                                row = {'path':entry.path,'bytes':info.st_size,'mtime':info.st_mtime,'extension':ext,'priorityProject':is_priority}
                                log.write(json.dumps(row,ensure_ascii=False)+'\n')
                                counts[dirname] += 1
                    except OSError as exc:
                        errors.append({'path':entry.path,'error':type(exc).__name__})
        except OSError as exc:
            errors.append({'path':dirname,'error':type(exc).__name__})
        if directories % 500 == 0:
            log.flush()
            save(private/'LIVE.json',{'directories':directories,'files':files_seen,'audio':sum(counts.values()),'seconds':round(time.monotonic()-started,1),'frontier':len(stack)})
save(private/'FOLDERS.json',[{'path':p,'audioFiles':n} for p,n in counts.most_common()])
save(private/'ERRORS.json',errors)
save(private/'FRONTIER.json',stack)
result={'seconds':round(time.monotonic()-started,2),'directories':directories,'files':files_seen,
        'audioFiles':sum(counts.values()),'audioFolders':len(counts),'errors':len(errors),
        'skips':dict(skips),'remainingDirectories':len(stack),'completeWithinDeclaredScope':not stack}
save(out/'RESULTS.json',result)
print(json.dumps(result),flush=True)
