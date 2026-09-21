import pathlib, sys, ast
S = pathlib.Path('C:/Users/usuario/AppData/Local/Temp/claude/d--Perfil-Escritorio-ETC-Programacion-BAXY-DEFINITIVO/250e1a56-9daa-4ae6-a51f-44fe3a271a6d/scratchpad')
base = (S / 'build_video1955.py').read_text(encoding='utf-8')
s = base
def sub(old, new, count=None):
    global s
    n = s.count(old)
    if n == 0 or (count is not None and n != count):
        raise SystemExit(f'MISSING/AMBIGUOUS ({n}, expected {count}): ' + old[:100])
    s = s.replace(old, new)
for panel in sorted(pathlib.Path('.').glob('panel_typed_*.py')):
    s = base
    exec(compile(panel.read_text(encoding='utf-8'), panel.name, 'exec'), globals())
    ast.parse(s)
    print('ok', panel.name, 'disney refs:', s.count('disney_bare_request'), 'video1955 refs:', s.count('video1955'))
