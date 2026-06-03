"""Limpia MI desastre del test de Word: cierra las Calculadoras de prueba + el
diálogo Buscar/Reemplazar. NO toca el Word del user (podría tener trabajo sin
guardar) — eso lo deja para él (su doc en disco está intacto, nunca se guardó)."""
import ctypes, time, win32gui
try: import psutil
except Exception: psutil=None
u=ctypes.windll.user32

killed=[]
if psutil:
    for p in psutil.process_iter(['pid','name']):
        if (p.info.get('name') or '').lower()=='calculatorapp.exe':
            try: p.kill(); killed.append(p.info['pid'])
            except Exception as e: print('no maté',p.info['pid'],e)
print('Calculadoras de prueba cerradas:', killed)

def find(sub):
    out=[]
    def cb(h,_):
        if sub in win32gui.GetWindowText(h) and win32gui.IsWindowVisible(h): out.append(h)
        return True
    win32gui.EnumWindows(cb,None); return out

for h in find('Buscar y reemplazar'):
    u.SendMessageW(h,0x0010,0,0)   # WM_CLOSE — cierra el diálogo, no guarda nada
    print('cerré el diálogo Buscar/Reemplazar')
    time.sleep(0.4)

print('Word con tu doc Hito_5: lo DEJO INTACTO para vos =', bool(find('Hito_5_completado')))
print('[done] tu archivo en disco sigue sin cambios (nunca guardé)')
