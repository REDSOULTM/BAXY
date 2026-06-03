"""Cierra el Notepad de PRUEBA (acumuló todo mi texto de test: 'Hola undo desde
emma4...'). Es 100% mío (el user no tenía Notepad abierto). Mata su proceso por el
PID de la ventana (Win11 Notepad = UWP, un solo proceso con pestañas). NO guarda."""
import ctypes, win32gui, win32process
k=ctypes.windll.kernel32
killed=[]
def cb(h,_):
    t=win32gui.GetWindowText(h)
    # solo el Notepad con MI texto de prueba o título de Notepad
    if win32gui.IsWindowVisible(h) and ("Bloc de notas" in t or "Notepad" in t or "emma4" in t):
        pid=win32process.GetWindowThreadProcessId(h)[1]
        hp=k.OpenProcess(0x0001,False,pid)
        if hp:
            ok=bool(k.TerminateProcess(hp,0)); k.CloseHandle(hp)
            killed.append((pid,t[:40],ok))
    return True
win32gui.EnumWindows(cb,None)
print('Notepad de prueba cerrado:', killed or 'ya no había')
