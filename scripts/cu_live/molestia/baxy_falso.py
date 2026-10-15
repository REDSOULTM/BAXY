"""«BAXY falso» para la autoprueba del medidor: otro proceso que molesta al usuario simulado de forma conocida.

Escenarios:
  fuera  roba el foco a una ventana propia de prueba durante 2 s y lo devuelve; salta el cursor con SetCursorPos
         a su ventana; teclea 5 letras con SendInput SIN marca en la ventana del usuario y una 0xB9 sin marca (la
         tecla que UIAutomationCore inyecta en nombre de BAXY).
  pausa  espera a la pausa del simulador (lee midiendo.json) y, dentro de ella, roba el foco, salta el cursor,
         teclea 3 letras CON la marca de BAXY en su propia ventana y devuelve foco y cursor como estaban (ida y
         vuelta del cursor dentro de la ráfaga).
  tarde  como pausa, pero devuelve cursor y foco 0,6 s DESPUÉS de que el simulador vuelve a teclear: la ráfaga no
         está restaurada al evaluarla y queda «restaurada tarde» con su retraso.
Escribe su cronología en --salida. Sólo toca su propia ventana y la del usuario simulado.
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes as wt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w32  # noqa: E402
from w32 import user32, kernel32  # noqa: E402

TITLE = "BAXY falso prueba molestia"
USER_TITLE = "BAXY usuario simulado"
PM_REMOVE = 1
LOG = []


def pump(seconds):
    end = time.time() + seconds
    msg = wt.MSG()
    while True:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        left = end - time.time()
        if left <= 0:
            return
        time.sleep(min(0.01, left))


def log(step, **kw):
    LOG.append({"t": round(time.time(), 3), "paso": step, **kw})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("escenario", choices=["fuera", "pausa", "tarde"])
    ap.add_argument("--control", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    w32.dpi_aware()
    user = user32.FindWindowW(None, USER_TITLE)
    if not user:
        print("no encuentro la ventana del usuario simulado", file=sys.stderr)
        return 2
    hinst = kernel32.GetModuleHandleW(None)
    wa = w32.work_area()
    w, h = 420, 300
    x, y = (wa[0] + wa[2] - w) // 2, (wa[1] + wa[3] - h) // 2
    mine = user32.CreateWindowExW(0, "STATIC", TITLE, w32.WS_OVERLAPPEDWINDOW, x, y, w, h, None, None, hinst, None)
    pump(0.2)
    center = (x + w // 2, y + h // 2)
    try:
        if a.escenario == "fuera":
            pump(1.0)
            user32.ShowWindow(mine, w32.SW_SHOWNORMAL)
            ok = w32.bring_front(mine)
            log("robo_foco", ok=ok)
            pump(2.0)
            ok = w32.bring_front(user, show=False)
            log("devuelve_foco", ok=ok)
            pump(0.8)
            user32.SetCursorPos(*center)
            log("setcursorpos", x=center[0], y=center[1])
            pump(0.6)
            front = user32.GetForegroundWindow() == user
            for ch in "qxjkw":
                w32.send_char(ch, 0)
                pump(0.03)
            log("teclea_sin_marca", n=5, usuario_delante=front)
            w32.send_vk(0xB9, 0)
            pump(0.05)
            log("tecla_uia_sin_marca", vk=0xB9)
        else:
            with open(os.path.join(a.control, "midiendo.json"), encoding="utf-8") as f:
                m = json.load(f)
            t0, cycle = m["t0"], m["escribe_s"] + m["pausa_s"]
            now = time.time()
            c = max(0, int((now - t0) // cycle))
            while t0 + c * cycle + m["escribe_s"] + 0.35 < now + 0.5:
                c += 1
            pump(t0 + c * cycle + m["escribe_s"] + 0.35 - time.time())
            orig = w32.cursor()
            user32.ShowWindow(mine, w32.SW_SHOWNORMAL)
            ok = w32.bring_front(mine)
            log("robo_foco_en_pausa", ok=ok)
            user32.SetCursorPos(*center)
            log("setcursorpos", x=center[0], y=center[1])
            for ch in "abc":
                w32.send_char(ch, w32.BAXY_MARK)
                pump(0.02)
            log("teclea_con_marca_en_su_ventana", n=3)
            limit = t0 + c * cycle + cycle
            if a.escenario == "tarde":
                # Espera a que el simulador vuelva a teclear (y evalúe la ráfaga) y devuelve 0,6 s después: primero
                # el cursor y luego el foco, así el simulador no lo recupera antes por su cuenta.
                pump(limit + 0.6 - time.time())
                user32.SetCursorPos(*orig)
                ok = w32.bring_front(user, show=False)
                log("restaura_tarde", ok=ok, x=orig[0], y=orig[1], tras_volver_ms=int((time.time() - limit) * 1000))
            else:
                ok = w32.bring_front(user, show=False)
                user32.SetCursorPos(*orig)
                log("restaura", ok=ok, x=orig[0], y=orig[1])
                log("margen_hasta_teclear_ms", ms=int((limit - time.time()) * 1000))
            pump(0.3)
    finally:
        user32.DestroyWindow(mine)
        with open(a.salida, "w", encoding="utf-8", newline="\n") as f:
            json.dump(LOG, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
