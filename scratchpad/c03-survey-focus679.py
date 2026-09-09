"""Exercise H0104 and six declared language/order/reference variants in product."""
from pathlib import Path
from datetime import datetime, timezone
import ctypes as c
from ctypes import wintypes as w
import json
import os
import psutil

root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-focus679-private'
private.mkdir(exist_ok=False)
assert psutil.virtual_memory().available>=2700*2**20

def foreground_snapshot():
    u=c.WinDLL('user32',use_last_error=True)
    u.GetForegroundWindow.restype=w.HWND
    u.GetWindowTextLengthW.argtypes=[w.HWND]
    u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
    u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    u.IsZoomed.argtypes=[w.HWND]
    u.IsIconic.argtypes=[w.HWND]
    handle=u.GetForegroundWindow()
    assert handle
    title=c.create_unicode_buffer(u.GetWindowTextLengthW(handle)+1)
    assert u.GetWindowTextW(handle,title,len(title))>=0
    pid=w.DWORD()
    u.GetWindowThreadProcessId(handle,c.byref(pid))
    state='minimized' if u.IsIconic(handle) else 'maximized' if u.IsZoomed(handle) else 'normal'
    return {'utc':datetime.now(timezone.utc).isoformat(),'handle':int(handle),'title':title.value,
            'pid':pid.value,'state':state,'process':psutil.Process(pid.value).name()}

def save_snapshot(name):
    (private/name).write_text(json.dumps(foreground_snapshot(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

survey=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-survey-requirements336-private/requirements.jsonl'
with survey.open(encoding='utf-8-sig') as stream:
    requirement=next(r for line in stream if (r:=json.loads(line))['case_id']=='H0104')
assert requirement['literal']=='qué ventana está activa' and requirement['expected_capability'] is True
assert requirement['verification_status']=='open'
specs=[
    ('H0104',requirement['literal'],'window.active',None),
    ('focus-temporal-en','Which window is active right now?','window.active',None),
    ('focus-order-es','Ahora mismo, ¿qué ventana tiene el foco?','window.active',None),
    ('focus-mixed','Baxy, ¿qué window tiene focus ahora?','window.active',None),
    ('focus-reference-es','¿Y ahora cuál está activa?','window.active',None),
    ('focus-title-es','Dime el nombre de la ventana que está en primer plano.','window.active',None),
    ('focus-courtesy-en','Please tell me which window currently has focus.','window.active',None),
]
source=(root/'scratchpad/c03-window-product634.py').read_text(encoding='utf-8')
source=source.replace('window-product634','survey-focus679').replace('window-profile634','survey-focus-profile679')
source=source.replace('private.mkdir(exist_ok=False)','assert private.is_dir()')
start=source.index('specs=[')
end=source.index('panel=[]',start)
source=source[:start]+'specs='+repr(specs)+'\n'+source[end:]
source=source.replace("case.startswith('H0040')", "case == 'H0104'")
source=source.replace('Shared source633 product','Shared source676 product')
source=source.replace('Eight named application queries with ES/EN/order/name variation, two foreground controls, missing volume and negative constraint.',
    'Exact owner H0104 plus six declared ES/EN/mixed, order, title and reference variants. Each must freshly read window.active, preserve independently observed foreground title/state and requested language. Before/after Win32 snapshots are read-only; no UI or voice credit.')
source=source.replace("'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',", "'src/baxy_mind/window_prose_facts.py', 'src/baxy_mind/request_reading.py', 'src/baxy_mind/effect_intent.py', 'src/baxy_mind/cpu_prose_adapter.py',")
save_snapshot('foreground-before.json')
try:
    exec(compile(source,__file__,'exec'))
finally:
    save_snapshot('foreground-after.json')
