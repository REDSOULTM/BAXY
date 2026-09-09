"""Same window panel with independent visible-HWND snapshots before and after."""
from pathlib import Path
from datetime import datetime,timezone
import ctypes as c
from ctypes import wintypes as w
import json,os,psutil
root=Path(__file__).resolve().parents[1]
evidence=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-enumeration-product639-private'
evidence.mkdir(exist_ok=False)
def sample():
    u=c.WinDLL('user32',use_last_error=True)
    callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    u.EnumWindows.argtypes=[callback,w.LPARAM]
    u.IsWindowVisible.argtypes=[w.HWND];u.IsWindowVisible.restype=w.BOOL
    u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    u.GetWindowRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
    found=[]
    @callback
    def collect(handle,_):
        if not u.IsWindowVisible(handle):return True
        pid=w.DWORD();u.GetWindowThreadProcessId(handle,c.byref(pid));rect=w.RECT()
        if not u.GetWindowRect(handle,c.byref(rect)) or rect.right<=rect.left or rect.bottom<=rect.top:return True
        try:process=psutil.Process(pid.value).name()
        except psutil.Error:return True
        found.append({'process':process,'pid':pid.value,'handle':int(handle),'width':rect.right-rect.left,'height':rect.bottom-rect.top})
        return True
    assert u.EnumWindows(collect,0)
    return {'utc':datetime.now(timezone.utc).isoformat(),'windows':found}
def save(name):
    (evidence/name).write_text(json.dumps(sample(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
save('windows-before.json')
source=(root/'scratchpad/c03-package-product637.py').read_text(encoding='utf-8')
source=source.replace('package-product637','enumeration-product639').replace('package-profile637','enumeration-profile639').replace('Shared source636 product','Shared source638 product')
# This wrapper creates the private directory to keep both independent snapshots
# beside the product logs; remove only the nested creation, never its assertions.
source=source.replace("exec(compile(source,__file__,'exec'))", "source=source.replace('private.mkdir(exist_ok=False)', 'assert private.is_dir()')\nexec(compile(source,__file__,'exec'))")
try:
    exec(compile(source,__file__,'exec'))
finally:
    save('windows-after.json')
