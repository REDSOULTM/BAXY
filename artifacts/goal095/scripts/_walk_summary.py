import json, os, sys, time, hashlib
from pathlib import Path

SKIP_DIR_NAMES = {'.git'}  # still count files inside .git? For git identity we skip hashing .git internals in hash mode; for counts we INCLUDE .git as part of tree completeness.

def walk_summary(root: Path, skip_git_dir: bool = False):
    files = 0
    dirs = 0
    bytes_ = 0
    errors = []
    newest = None
    oldest = None
    newest_rel = None
    empty_files = 0
    start = time.perf_counter()
    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False, onerror=lambda e: errors.append(str(e))):
            if skip_git_dir:
                dirnames[:] = [d for d in dirnames if d != '.git']
            dirs += 1
            for name in filenames:
                p = os.path.join(dirpath, name)
                try:
                    st = os.lstat(p)
                except OSError as e:
                    errors.append(f'{p}: {e}')
                    continue
                files += 1
                bytes_ += st.st_size
                if st.st_size == 0:
                    empty_files += 1
                m = st.st_mtime
                if newest is None or m > newest:
                    newest = m
                    newest_rel = os.path.relpath(p, root)
                if oldest is None or m < oldest:
                    oldest = m
    except OSError as e:
        errors.append(str(e))
    return {
        'root_logical': root.name,
        'files': files,
        'dirs': dirs,
        'bytes': bytes_,
        'empty_files': empty_files,
        'newest_mtime_unix': newest,
        'oldest_mtime_unix': oldest,
        'newest_rel': newest_rel,
        'errors': errors[:50],
        'error_count': len(errors),
        'elapsed_s': round(time.perf_counter() - start, 3),
    }

roots = [
    Path(r'D:\Perfil\Escritorio\ETC\Programacion\BAXY'),
    Path(r'D:\Perfil\Escritorio\ETC\Programacion\Carter OS AI'),
    Path(r'D:\Perfil\Escritorio\ETC\Programacion\FunctionGemma'),
    Path(r'D:\Perfil\Escritorio\ETC\Programacion\Probando Gemma 4'),
    Path(r'D:\BAXY'),
    Path(r'D:\BAXY\FunctionGemma'),
    Path(r'D:\Perfil\Escritorio\ETC\Programacion\Probando schemas'),
]
outp = Path(sys.argv[1])
label = sys.argv[2]
results = []
for r in roots:
    rec = {'asked': str(r), 'exists': r.exists()}
    if r.exists():
        rec.update(walk_summary(r))
    results.append(rec)
    print(f"{r} exists={r.exists()} files={rec.get('files')} bytes={rec.get('bytes')} newest={rec.get('newest_rel')} err={rec.get('error_count')} t={rec.get('elapsed_s')}", flush=True)
outp.write_text(json.dumps(results, indent=2), encoding='utf-8')
print('WROTE', outp, 'label', label, flush=True)
