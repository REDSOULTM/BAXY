"""Read actual process AUMIDs without opening, focusing or closing applications."""
from pathlib import Path
from datetime import datetime, timezone
import ctypes as c
from ctypes import wintypes as w
import hashlib,json,os,psutil,subprocess
root=Path(__file__).resolve().parents[1]
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-package-identity635-private'
out=root/'artifacts/comprobaciones/C03/astra-package-identity635'
private.mkdir(exist_ok=False);out.mkdir(exist_ok=False)
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
k=c.WinDLL('kernel32',use_last_error=True);u=c.WinDLL('user32',use_last_error=True)
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.CloseHandle.argtypes=[w.HANDLE]
k.GetApplicationUserModelId.argtypes=[w.HANDLE,c.POINTER(w.UINT),w.LPWSTR];k.GetApplicationUserModelId.restype=w.LONG
callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
u.EnumWindows.argtypes=[callback,w.LPARAM]
u.IsWindowVisible.argtypes=[w.HWND];u.IsWindowVisible.restype=w.BOOL
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
windows={}
@callback
def collect(hwnd,_):
    if u.IsWindowVisible(hwnd):
        pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        windows.setdefault(pid.value,[]).append(int(hwnd))
    return True
u.EnumWindows(collect,0)
observations=[]
for pid,handles in windows.items():
    try: name=psutil.Process(pid).name()
    except psutil.Error: continue
    handle=k.OpenProcess(0x1000,False,pid)
    row={'pid':pid,'process_name':name,'visible_handles':handles,'open_error':None,'aumid':None}
    if not handle: row['open_error']=c.get_last_error()
    else:
        try:
            length=w.UINT();first=k.GetApplicationUserModelId(handle,c.byref(length),None)
            row.update(first_result=first,length=length.value)
            if first==122 and 0<length.value<=1024:
                buffer=c.create_unicode_buffer(length.value)
                second=k.GetApplicationUserModelId(handle,c.byref(length),buffer)
                row['second_result']=second
                if second==0: row['aumid']=buffer.value
        finally:k.CloseHandle(handle)
    observations.append(row)
write(private/'observations.json',observations)
catalog=json.loads(subprocess.check_output(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',
    "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); @(Get-StartApps | Where-Object { $_.Name -in @('Bloc de notas','Paint','Spotify','Calculadora') }) | ConvertTo-Json -Compress"],encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW))
write(private/'catalog.json',catalog)
matches=[{'name':entry['Name'],'aumid':entry['AppID'],'matched_processes':[
    r['process_name'] for r in observations if r['aumid']==entry['AppID']]} for entry in catalog]
result={'utc':datetime.now(timezone.utc).isoformat(),'source_modified':False,'side_effects':False,
    'catalog_matches':matches,'visible_processes':len(observations),
    'unexpected_query_errors':[r for r in observations if r['open_error'] or r.get('first_result') not in [122,15703]],
    'private_hashes':{n:sha(private/n) for n in ['observations.json','catalog.json']},
    'documentation':'https://learn.microsoft.com/en-us/windows/win32/api/appmodel/nf-appmodel-getapplicationusermodelid'}
write(out/'RESULT.json',result)
print(json.dumps(result,ensure_ascii=False))
