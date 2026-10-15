"""Registro pasivo del arnés en vivo: input del dueño y procesos nacidos, para el libro del lote (libro_lote.ps1).

El libro sólo puede dar por quieto al dueño, o atribuir un proceso al lote, con un registro que cubra TODO el tramo:
desde la foto del lote hasta el cierre. El medidor de molestia sólo mide dentro de cada caso (desde la línea
«runtime»), así que los huecos (estados base, esperas de GPU y batería, entre casos, una tanda entera) quedaban sin
registro y el libro los suponía quietos. Este registro corre desde antes de la foto hasta después del cierre:
  - ganchos de bajo nivel de teclado y ratón: input del dueño = todo lo que no lleva la marca del simulador
    (w32.SIM_MARK) ni la de BAXY (w32.BAXY_MARK). Lo inyectado sin marca cuenta como del dueño (Deskflow/Synergy
    inyectan el input real del dueño sin marca): ante la duda, el dueño estaba activo. Sólo se guardan instantes.
  - si GetLastInputInfo ve input más nuevo que el último que vieron los ganchos (Windows quita un gancho lento sin
    avisar), ese tramo no visto cuenta ENTERO como input del dueño (falla cerrado: nadie se da por quieto donde los
    ganchos no miraron), queda en «cortes» y los ganchos se vuelven a poner. Antes la cobertura se cortaba para
    siempre: en la ronda 7 (2026-10-08) cada registro se rompió a los 2-10 min y el libro dio al dueño por activo en
    casi todos los casos, así que no cerró nada de lo que abrieron (Reloj, OneNote, Word con su aviso, OBS...). Sólo
    si los ganchos no se pueden volver a poner la cobertura se corta: «cubierto_hasta» deja de avanzar y «roto» dice
    desde cuándo.
  - procesos: cada 0,3 s los pids nuevos con su padre, nombre y hora de inicio, para seguir el linaje de un proceso
    aunque su padre (el powershell de un estado, BAXY) ya haya salido.
Escribe --salida cada 0,5 s (reemplazo atómico): {cubierto_desde, cubierto_hasta, intervalos_dueno, procesos, raiz,
roto, cortes, fallos_bucle, reinicios}. Para con el archivo --parar o cuando sale --raiz (el bash o powershell del
arnés que lo lanzó): nunca queda vivo solo.

La raíz sólo se da por muerta con pruebas repetidas (RAIZ_SEGUIDAS lecturas seguidas: no existe, o su hora de inicio es
otra): en la pasada r9 (2026-10-08 12:07) el registro salió solo con lote.sh vivo, por una lectura de psutil que falló
(AccessDenied o carga) y que el bucle tomaba como «raíz muerta»; desde ahí el libro dio al dueño por activo y no cerró
nada en 2 h. Cualquier otra excepción se reintenta, y el bucle nunca muere por una: queda en «fallos_bucle» y sigue.
--continuar retoma un registro que murió sobre el mismo archivo (lote.sh, registro_vigilar): conserva lo escrito y el
hueco sin registro cuenta ENTERO como input del dueño (falla cerrado), en «cortes» y en «reinicios».

Uso: py -3.12 registro_dueno.py --salida registro.json --raiz <pid de Windows> [--parar archivo] [--continuar]
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes as wt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "molestia"))

GRACIA_S = 1.0       # dos instantes del dueño a menos de 1 s forman un intervalo
SONDEO_PROC_S = 0.3
ESCRITURA_S = 0.5
HOLGURA_HOOK_S = 1.0  # GetLastInputInfo puede ir hasta 1 s por delante de lo que vio el gancho
WM_REPONER = 0x8000 + 0x52  # WM_APP + 'R': el hilo de los ganchos los quita y los vuelve a poner
RAIZ_SEGUIDAS = 5    # lecturas seguidas (0,3 s cada una) que prueban la raíz muerta antes de salir
FALLOS_GUARDADOS = 20


def es_input_dueno(inyectado: bool, extra: int, sim_mark: int, baxy_mark: int) -> bool:
    """Input real, o inyectado sin una marca conocida: del dueño (falla cerrado)."""
    if not inyectado:
        return True
    return extra not in (sim_mark, baxy_mark)


def agregar_instante(intervalos: list[list[float]], t: float, gracia: float = GRACIA_S) -> None:
    if intervalos and t - intervalos[-1][1] <= gracia:
        intervalos[-1][1] = max(intervalos[-1][1], t)
    else:
        intervalos.append([t, t])


def tramo_no_visto(ultimo_input_sistema: float | None, ultimo_gancho: float | None) -> list[float] | None:
    """[desde, hasta] del input que el sistema vio y los ganchos no (Windows los quitó), o None.

    Ese tramo entero cuenta como input del dueño: lo que nadie miró nunca se da por quieto."""
    if ultimo_input_sistema is None or ultimo_gancho is None:
        return None
    if ultimo_input_sistema > ultimo_gancho + HOLGURA_HOOK_S:
        return [ultimo_gancho, ultimo_input_sistema]
    return None


def veredicto_raiz(lectura: str, seguidas: int, n: int = RAIZ_SEGUIDAS) -> tuple[int, bool]:
    """(seguidas, terminar) tras una lectura de la raíz: 'viva' | 'muerta' (no existe, u otra hora de inicio) | 'duda'.

    Sólo 'muerta' n veces seguidas termina; 'viva' pone la cuenta a cero; 'duda' (cualquier otra excepción: AccessDenied,
    carga) no cuenta para ningún lado y se vuelve a leer."""
    if lectura == "viva":
        return 0, False
    if lectura == "muerta":
        seguidas += 1
        return seguidas, seguidas >= n
    return seguidas, False


def retomar(previo: dict | None, ahora: float, raiz: int) -> dict | None:
    """Lo que un registro nuevo hereda de uno que murió sobre el mismo archivo, o None si no hay nada que retomar.

    El hueco entre su último cubierto_hasta y ahora cuenta entero como input del dueño (nadie miró: falla cerrado)."""
    if not isinstance(previo, dict) or previo.get("raiz") != raiz or previo.get("cubierto_desde") is None:
        return None
    hasta = previo.get("cubierto_hasta") or previo["cubierto_desde"]
    intervalos = [list(x) for x in previo.get("intervalos_dueno") or []]
    hueco = [float(hasta), float(ahora)]
    agregar_tramo(intervalos, hueco)
    return {"desde": previo["cubierto_desde"], "intervalos": intervalos, "roto": previo.get("roto"),
            "cortes": list(previo.get("cortes") or []) + [[round(hueco[0], 3), round(hueco[1], 3)]],
            "reinicios": list(previo.get("reinicios") or []) + [[round(hueco[0], 3), round(hueco[1], 3)]],
            "procesos": list(previo.get("procesos") or []), "fallos": list(previo.get("fallos_bucle") or [])}


def agregar_tramo(intervalos: list[list[float]], tramo: list[float], gracia: float = GRACIA_S) -> None:
    """Agrega un tramo del dueño al final de la lista (en orden), uniéndolo con el último si se tocan."""
    if intervalos and tramo[0] - intervalos[-1][1] <= gracia:
        intervalos[-1][0] = min(intervalos[-1][0], tramo[0])
        intervalos[-1][1] = max(intervalos[-1][1], tramo[1])
    else:
        intervalos.append([tramo[0], tramo[1]])


def cobertura_hasta(ahora: float, ultimo_input_sistema: float | None, ultimo_gancho: float | None,
                    roto: float | None) -> tuple[float, float | None]:
    """(cubierto_hasta, roto): la cobertura se corta en cuanto el sistema vio input que los ganchos no vieron."""
    if roto is not None:
        return roto, roto
    if ultimo_input_sistema is not None and ultimo_input_sistema > (ultimo_gancho or 0.0) + HOLGURA_HOOK_S:
        corte = ultimo_gancho or 0.0
        return corte, corte
    return ahora, None


class Registro:
    def __init__(self, salida: str, raiz: int, parar: str | None, continuar: bool = False):
        import psutil  # noqa: PLC0415 — sólo en vivo; los tests usan las funciones puras
        import w32  # noqa: PLC0415

        self.psutil = psutil
        self.w32 = w32
        self.salida = salida
        self.raiz = raiz
        self.parar = parar
        self.lock = threading.Lock()
        self.intervalos: list[list[float]] = []
        self.ultimo_gancho: float | None = None
        self.roto: float | None = None
        self.cortes: list[list[float]] = []
        self.procesos: dict[tuple[int, float], dict] = {}
        self.vistos: set[int] = set()
        self.fin = threading.Event()
        self.desde: float | None = None
        self.continuar = continuar
        self.reinicios: list[list[float]] = []
        self.fallos: list[list] = []
        self.raiz_seguidas = 0
        self._kb = w32.HOOKPROC(self._kb_hook)
        self._ms = w32.HOOKPROC(self._ms_hook)
        self.hooks: list = []
        self.raiz_inicio: float | None = None
        self.raiz_inicio = self._inicio_raiz()

    def _inicio_raiz(self) -> float | None:
        try:
            return self.psutil.Process(self.raiz).create_time()
        except Exception:  # noqa: BLE001 — se vuelve a leer en el bucle (_leer_raiz)
            return None

    def _visto(self, inyectado: bool, extra: int) -> None:
        t = time.time()
        with self.lock:
            self.ultimo_gancho = t
            if es_input_dueno(inyectado, extra, self.w32.SIM_MARK, self.w32.BAXY_MARK):
                agregar_instante(self.intervalos, t)

    def _kb_hook(self, code, wparam, lparam):
        try:
            if code == self.w32.HC_ACTION:
                k = self.w32.KBDLLHOOKSTRUCT.from_address(lparam)
                self._visto(bool(k.flags & self.w32.LLKHF_INJECTED), int(k.dwExtraInfo))
        except Exception:  # noqa: BLE001 — un fallo nunca bloquea el teclado del dueño
            pass
        return self.w32.user32.CallNextHookEx(None, code, wparam, lparam)

    def _ms_hook(self, code, wparam, lparam):
        try:
            if code == self.w32.HC_ACTION:
                m = self.w32.MSLLHOOKSTRUCT.from_address(lparam)
                self._visto(bool(m.flags & self.w32.LLMHF_INJECTED), int(m.dwExtraInfo))
        except Exception:  # noqa: BLE001
            pass
        return self.w32.user32.CallNextHookEx(None, code, wparam, lparam)

    def _ultimo_input_sistema(self) -> float | None:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]
        li = LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(li)
        if not self.w32.user32.GetLastInputInfo(ctypes.byref(li)):
            return None
        ahora_tick = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return time.time() - ((ahora_tick - li.dwTime) & 0xFFFFFFFF) / 1000.0

    def _sondear_procesos(self) -> None:
        ps = self.psutil
        for pid in set(ps.pids()) - self.vistos:
            self.vistos.add(pid)
            try:
                p = ps.Process(pid)
                nacio = p.create_time()
                self.procesos[(pid, round(nacio, 3))] = {"pid": pid, "padre": p.ppid(),
                                                        "nombre": os.path.splitext(p.name())[0], "nacio": round(nacio, 3)}
            except Exception:  # noqa: BLE001 — salió o es del sistema
                continue
        vivos = set(ps.pids())
        self.vistos &= vivos  # un pid reutilizado se vuelve a leer

    def _leer_raiz(self) -> str:
        """'viva' | 'muerta' (no existe, u otra hora de inicio: el pid es de otro proceso) | 'duda' (otra excepción)."""
        try:
            inicio = self.psutil.Process(self.raiz).create_time()
        except self.psutil.NoSuchProcess:
            return "muerta"
        except Exception:  # noqa: BLE001 — AccessDenied, carga: no prueba nada, se vuelve a leer
            return "duda"
        if self.raiz_inicio is None:  # la primera lectura falló: la hora de inicio se toma ahora
            self.raiz_inicio = inicio
        return "viva" if inicio == self.raiz_inicio else "muerta"

    def _raiz_viva(self) -> bool:
        """False sólo tras RAIZ_SEGUIDAS lecturas seguidas que prueban la raíz muerta (veredicto_raiz)."""
        self.raiz_seguidas, terminar = veredicto_raiz(self._leer_raiz(), self.raiz_seguidas)
        return not terminar

    def _fallo(self, e: BaseException) -> None:
        with self.lock:
            self.fallos.append([round(time.time(), 3), f"{type(e).__name__}: {e}"[:200]])
            del self.fallos[:-FALLOS_GUARDADOS]

    def _escribir(self) -> None:
        sistema = self._ultimo_input_sistema()
        reponer = False
        with self.lock:
            tramo = None if self.roto is not None else tramo_no_visto(sistema, self.ultimo_gancho or self.desde)
            if tramo is not None:
                # The hooks missed input (Windows dropped them): that whole span is the person's, and they go back on.
                agregar_tramo(self.intervalos, tramo)
                self.cortes.append([round(tramo[0], 3), round(tramo[1], 3)])
                self.ultimo_gancho = tramo[1]
                reponer = True
            hasta, self.roto = cobertura_hasta(time.time(), sistema, self.ultimo_gancho or self.desde, self.roto)
            doc = {"version": 1, "raiz": self.raiz, "cubierto_desde": self.desde, "cubierto_hasta": round(hasta, 3),
                   "roto": self.roto, "cortes": list(self.cortes), "fallos_bucle": list(self.fallos),
                   "reinicios": list(self.reinicios),
                   "intervalos_dueno": [[round(s, 3), round(e, 3)] for s, e in self.intervalos],
                   "procesos": sorted(self.procesos.values(), key=lambda x: x["nacio"])}
        if reponer:
            self.w32.user32.PostThreadMessageW(self.tid, WM_REPONER, 0, 0)
        tmp = self.salida + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, ensure_ascii=True)
        for _ in range(20):
            try:
                os.replace(tmp, self.salida)
                return
            except PermissionError:  # el libro lo está leyendo
                time.sleep(0.05)

    def bucle(self) -> None:
        # What already runs at the start is not read (reading ~500 processes takes seconds): the ledger reads the live
        # ones itself, and a child whose parent died unread gets no provenance (fail closed). Nothing slow ever runs
        # on the hook thread: its message pump must keep turning or Windows times the hooks out and drops them.
        # An exception never ends this loop (pasada r9: this thread IS the record): it goes to fallos_bucle and the next
        # round tries again. Only the stop file or a root proven dead RAIZ_SEGUIDAS times in a row end it.
        while not self.fin.is_set():
            try:
                self.vistos = set(self.psutil.pids())
                break
            except Exception as e:  # noqa: BLE001
                self._fallo(e)
                time.sleep(SONDEO_PROC_S)
        ultimo = 0.0
        while not self.fin.is_set():
            try:
                self._sondear_procesos()
                if time.time() - ultimo >= ESCRITURA_S:
                    self._escribir()
                    ultimo = time.time()
                if (self.parar and os.path.exists(self.parar)) or not self._raiz_viva():
                    break
            except Exception as e:  # noqa: BLE001
                self._fallo(e)
            time.sleep(SONDEO_PROC_S)
        try:
            self._escribir()
        except Exception as e:  # noqa: BLE001
            self._fallo(e)
        self.fin.set()
        self.w32.user32.PostThreadMessageW(self.tid, self.w32.WM_QUIT, 0, 0)

    def _poner_ganchos(self) -> bool:
        w32 = self.w32
        for h in self.hooks:
            w32.user32.UnhookWindowsHookEx(h)
        self.hooks = []
        hinst = w32.kernel32.GetModuleHandleW(None)
        for kind, proc in ((w32.WH_KEYBOARD_LL, self._kb), (w32.WH_MOUSE_LL, self._ms)):
            h = w32.user32.SetWindowsHookExW(kind, proc, hinst, 0)
            if not h:
                return False
            self.hooks.append(h)
        return True

    def _retomar(self) -> None:
        """--continuar: hereda el registro que murió sobre este archivo (retomar); sin uno legible empieza de cero."""
        try:
            with open(self.salida, encoding="utf-8") as f:
                previo = json.load(f)
        except Exception:  # noqa: BLE001
            previo = None
        r = retomar(previo, self.desde, self.raiz)
        if r is None:
            return
        self.desde = r["desde"]
        self.intervalos, self.cortes, self.reinicios, self.fallos = r["intervalos"], r["cortes"], r["reinicios"], r["fallos"]
        self.roto = r["roto"]
        for x in r["procesos"]:
            try:
                self.procesos[(int(x["pid"]), round(float(x["nacio"]), 3))] = x
            except Exception:  # noqa: BLE001
                continue

    def correr(self) -> int:
        w32 = self.w32
        self.tid = w32.kernel32.GetCurrentThreadId()
        if not self._poner_ganchos():
            print(json.dumps({"registro": "sin_ganchos"}))
            return 4
        self.desde = round(time.time(), 3)
        self.ultimo_gancho = self.desde
        if self.continuar:
            self._retomar()
        threading.Thread(target=self.bucle, daemon=True).start()
        msg = wt.MSG()
        while w32.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if not msg.hWnd and msg.message == WM_REPONER:
                # Hooks dropped by Windows go back on this same thread, the one pumping their messages. If they cannot,
                # the coverage stops for good there (roto).
                if not self._poner_ganchos():
                    with self.lock:
                        self.roto = self.ultimo_gancho or time.time()
                continue
            w32.user32.TranslateMessage(ctypes.byref(msg))
            w32.user32.DispatchMessageW(ctypes.byref(msg))
        for h in self.hooks:
            w32.user32.UnhookWindowsHookEx(h)
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--raiz", type=int, required=True)
    ap.add_argument("--parar", default=None)
    ap.add_argument("--continuar", action="store_true")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    return Registro(os.path.abspath(a.salida), a.raiz, a.parar, a.continuar).correr()


if __name__ == "__main__":
    sys.exit(main())
