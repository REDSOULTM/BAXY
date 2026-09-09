"""Same twenty product cases plus four declared foreground language variants."""
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w


def foreground655():
    u = c.WinDLL('user32', use_last_error=True)
    u.GetForegroundWindow.restype = w.HWND
    u.GetWindowTextLengthW.argtypes = [w.HWND]
    u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    handle = u.GetForegroundWindow()
    size = u.GetWindowTextLengthW(handle)
    title = c.create_unicode_buffer(size + 1)
    u.GetWindowTextW(handle, title, size + 1)
    return {'handle': int(handle or 0), 'title': title.value}

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-window-scope-product653.py').read_text(encoding='utf-8')
source = source.replace('window-scope-product653', 'language-product655').replace('window-scope-profile653', 'language-profile655').replace('Shared source652 product', 'Shared source654 product')
last = "exec(compile(source, __file__, 'exec'))"
assert source.count(last) == 1
extra = """specs += [
 ('focus-vocative-en','Baxy, which window has focus?','window.active',None),
 ('focus-temporal-en','Which window has focus right now?','window.active',None),
 ('focus-application-en','Which application has focus?','window.active',None),
 ('focus-variant-es','Baxy, ¿qué ventana está activa ahora?','window.active',None),
]
panel=[]"""
source = source.replace(last, """injection = 'source=source.replace('+repr('panel=[]')+', '+repr(extra)+')\\n'
inner_exec = "exec(compile(source,__file__,'exec'))"
reader_injection = 'source=source.replace('+repr("'src/baxy_mind/cpu_prose_adapter.py',")+', '+repr("'src/baxy_mind/request_reading.py', 'src/baxy_mind/cpu_prose_adapter.py',")+')\\n'
injection += 'source=source.replace('+repr(inner_exec)+', '+repr(reader_injection+inner_exec)+')\\n'
assert source.count('try:\\n    exec(') == 1
source=source.replace('try:\\n    exec(', injection+'try:\\n    exec(')
old_snapshot = "return {'utc':datetime.now(timezone.utc).isoformat(),'windows':found}"
new_snapshot = "return {'utc':datetime.now(timezone.utc).isoformat(),'windows':found,'foreground':foreground655()}"
prefix_exec = "exec(compile(prefix,__file__,'exec'))"
assert source.count(prefix_exec) == 1
source=source.replace(prefix_exec, 'prefix=prefix.replace('+repr(old_snapshot)+', '+repr(new_snapshot)+')\\n'+prefix_exec)
source=source.replace('No communication authorized.', 'No communication authorized. Adds four declared foreground language variants after the original twenty; compare language and independently captured foreground.')
exec(compile(source, __file__, 'exec'))""")
exec(compile(source, __file__, 'exec'))
