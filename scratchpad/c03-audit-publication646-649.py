"""Verify combined-source validation and contextual/factual diagnostic evidence."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-audit-publication612-621.py').read_text(encoding='utf-8')
start = source.index('names='); end = source.index('verified=0', start)
source = source[:start]+"names=['context-source646','context-product647','package-scope648','window-fact-contract649','window-regression651']\n"+source[end:]
source = source.replace('d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425', '464603566c9dc66204cc75e45a79c8058063d0bb06fe6ff554bf56529e5ea73e')
exec(compile(source, __file__, 'exec'))
result = json.loads((base/'astra-window-regression651/RESULT.json').read_text(encoding='utf-8'))
assert result['full_exit'] == 0 and result['adopted']
for path, expected in result['git_source_files_lf'].items():
    data = (root/path).read_bytes().replace(b'\r\n', b'\n')
    if '--staged' in sys.argv:
        data = subprocess.check_output(['git', 'show', ':'+path], cwd=root)
    assert hashlib.sha256(data).hexdigest() == expected, path
print(json.dumps({'validated_source_files':len(result['git_source_files_lf']), 'lf_repository_bytes_verified':True}))
