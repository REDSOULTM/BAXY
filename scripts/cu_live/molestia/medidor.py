"""Medidor de molestia del arnés en vivo (goal v3, punto 0).

Un «usuario simulado» escribe en su propia ventana (un EDIT Win32, título «BAXY usuario simulado», nunca un Bloc
de notas) y mueve el ratón dentro de ella con un patrón fijo (2 s escribiendo a 8 car/s + 1 s de pausa) mientras
BAXY hace una misión. Ganchos de bajo nivel separan tres fuentes de input:
  - DUEÑO: input sin LLKHF_INJECTED/LLMHF_INJECTED. Pausa la atribución: nada se atribuye a BAXY dentro de su
    intervalo de actividad + 1 s, el simulador se detiene y el caso queda marcado «dueño activo».
    Del dueño sólo se guardan instantes, nunca qué tecla pulsó.
  - SIMULADOR: inyectado con dwExtraInfo = w32.SIM_MARK. Si su ventana no está delante el gancho se traga la
    tecla (devuelve 1) y la cuenta como carácter perdido: el simulador nunca teclea en una app ajena.
  - BAXY/AJENO: inyectado con w32.BAXY_MARK (BAXY; el producto la pone desde fable/cu-v3-pausa) o sin marca conocida (ajeno).
    La tecla 0xB9 sin marca lleva fuente «uia»: la inyecta UIAutomationCore cuando BAXY llama a un patrón UIA sobre una
    ventana que está detrás (diagnóstico r4a). Sigue contando como tecla de BAXY: la inyecta UIA en su nombre.
SetCursorPos no pasa por el gancho: un sondeo de GetCursorPos cada 10 ms detecta los saltos que ningún
movimiento enganchado explica. El simulador anota cada punto ANTES de mandarlo (con la máquina cargada el gancho llega
tarde y el sondeo veía su propio movimiento como un salto ajeno). La vuelta del cursor a la posición del usuario tras
un salto ajeno es una restauración, no un movimiento. SetWinEventHook(EVENT_SYSTEM_FOREGROUND) registra el primer
plano; un aviso cuya ventana no está delante es «transitorio» y se cuenta aparte (Windows lo emite aunque niegue
SetForegroundWindow), nunca como robo.

Ventana de medición: desde la señal de inicio (la línea «runtime» del events.jsonl del conductor, que la App
escribe justo antes de mandar el primer turno, o «ahora») hasta la señal de parada + 2 s. Al iniciar, la ventana
del usuario recupera el frente. Al final espera 1 s, mira si su ventana y su cursor volvieron, compara el texto
del EDIT con lo entregado (distancia de edición mínima) y escribe el JSON.

Uso:
  py -3.12 medidor.py medir --control DIR --salida molestia.json [--inicio ahora|eventos:RUTA] [--pausa 2]
      DIR/parar (archivo) detiene la medición; el medidor escribe DIR/listo.json y DIR/midiendo.json.
  py -3.12 medidor.py espera [--pausa 2] [--espera-max 1200]
      sólo espera a que el input REAL del dueño haga una pausa de --pausa s (sale 0; 4 si nunca la hace).
"""
import argparse
import collections
import ctypes
import json
import math
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes as wt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w32  # noqa: E402
from w32 import user32, kernel32  # noqa: E402

TITLE = "BAXY usuario simulado"
CLASS = "BaxyMolestiaUsuarioSimulado"
TEXT = "el usuario escribe tranquilo mientras baxy hace sus cosas "
CPS = 8.0            # caracteres por segundo del simulador
TYPE_S = 2.0         # tramo escribiendo
PAUSE_S = 1.0        # tramo en pausa
RATON_REST_S = 0.7   # --solo-raton: la mano quieta entre tramos (más que la pausa de 500 ms que BAXY espera)
OWNER_GRACE_S = 1.0  # tras input real del dueño, nada se atribuye a BAXY durante este margen
PAUSE_RULE_S = 0.4   # un acto ajeno está «dentro de pausa» si ni simulador ni dueño dieron input en los 400 ms previos
TAIL_S = 2.0         # la medición sigue 2 s tras la señal de parada
FINAL_WAIT_S = 1.0   # y 1 s más antes de comprobar ventana y cursor
CURSOR_TOL = 2       # px
POLL_S = 0.010
REMOTE_INPUT = ("deskflow", "synergy", "moonlight", "vibepollo", "sunshine", "barrier", "input-leap", "inputleap")
MAX_LOGGED_ACTS = 3000  # en el JSON; los contadores usan todos
# Una «ráfaga» es foco o cursor ajenos; se evalúa si quedaron como estaban. Las teclas que caen en la ventana del
# usuario y las peticiones de cierre no se restauran: cuentan aparte (teclas_baxy, insertados, cierres_pedidos).
NOT_IN_BURSTS = ("tecla_en_ventana_usuario", "cierre_pedido")
VK_UIA = 0xB9           # tecla que UIAutomationCore inyecta sin marca para ceder el primer plano a la app
SENT_TTL_S = 1.5        # un punto anotado por el simulador explica un salto durante este tiempo (y una sola vez)
LATE_FG_S = 1.0         # un aviso de primer plano de una ventana que dejó el frente hace menos de esto es «tardío»

WM_APP_SHOW = w32.WM_APP + 1
WM_APP_FRONT = w32.WM_APP + 2
WM_APP_FINISH = w32.WM_APP + 3


def remote_input_processes():
    """Procesos que inyectan input SIN marca (posible atribución errónea a BAXY)."""
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=20,
                             creationflags=0x08000000).stdout
    except Exception:  # noqa: BLE001
        return ["tasklist_no_disponible"]
    names = set()
    for line in out.splitlines():
        name = line.split('","')[0].strip('"').lower()
        if name.startswith(REMOTE_INPUT):
            names.add(name)
    return sorted(names)


def key_source(extra, vk):
    """Fuente de una tecla inyectada que no es del simulador: «baxy» (marca del producto), «uia» (0xB9 sin marca,
    UIAutomationCore en nombre de BAXY) o «ajeno»."""
    if extra == w32.BAXY_MARK:
        return "baxy"
    if extra == 0 and vk == VK_UIA:
        return "uia"
    return "ajeno"


def near(p, q, tol=CURSOR_TOL):
    return p is not None and q is not None and abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def common_len(a, b):
    """Largo de la subsecuencia común más larga (programación dinámica O(n·m), una fila a la vez). Con ella la
    distancia de edición mínima sin sustituciones da perdidos = len(a) - común e insertados = len(b) - común.
    difflib no da la alineación mínima sobre el texto periódico del simulador (pasada r18, v3-62: un solo carácter
    distinto salía como 115 borrados y 116 insertados)."""
    if len(a) < len(b):
        a, b = b, a
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if ca == cb else (prev[j] if prev[j] > cur[j - 1] else cur[j - 1]))
        prev = cur
    return prev[-1]


def typed_text(n):
    """Lo que el simulador mandó en sus n primeras teclas (TEXT en ciclo, desde el principio)."""
    return "".join(TEXT[i % len(TEXT)] for i in range(n))


def text_loss(delivered, text, sent="", unseen=0):
    """(perdidos_en_texto, insertados, entregados_sin_gancho) del texto que quedó en la ventana del usuario.

    delivered: lo que el gancho dejó pasar; text: lo que la ventana tiene al final; sent: todo lo que el simulador mandó;
    unseen: teclas suyas que el gancho no vio ni entregar ni tragar. Con la máquina cargada el gancho de bajo nivel
    puede no llegar a tiempo (Windows lo salta y la tecla pasa sin que el medidor la anote, junto a un primer plano
    transitorio de una app que arranca: v3-62, t-long-3). Una tecla así cuenta como entregada si está en la ventana:
    los caracteres de la ventana que sólo se alinean con lo mandado, hasta unseen, no son inserciones ajenas."""
    common = common_len(delivered, text)
    lost, inserted = len(delivered) - common, len(text) - common
    recovered = 0
    if unseen > 0 and inserted > 0 and sent:
        foreign = len(text) - common_len(sent, text)
        recovered = min(unseen, max(0, inserted - foreign))
    return lost, inserted - recovered, recovered


def transient_kind(root, t, fg_left):
    """Aviso de primer plano de una ventana que no está delante: «aviso_tardio» si esa ventana tuvo el frente y lo
    dejó hace menos de LATE_FG_S (el WinEvent llegó encolado), «sin_frente» si no (Windows avisa aunque niegue
    SetForegroundWindow: medido ret=False con evento)."""
    left = fg_left.get(root)
    return "aviso_tardio" if left is not None and 0 <= t - left <= LATE_FG_S else "sin_frente"


class Medidor:
    def __init__(self, args):
        self.args = args
        self.lock = threading.Lock()
        self.hinst = kernel32.GetModuleHandleW(None)
        self.hwnd = None
        self.edit = None
        self.hooks = []
        self.winevent = None
        self.t_hooks = None
        # dueño
        self.owner_last = None           # último input real
        self.owner_intervals = []        # [[ini, fin]] fusionados con huecos < OWNER_GRACE_S
        self.owner_events = 0            # durante la medición
        # simulador
        self.sim_last = None             # último input del simulador (también los tragados: el usuario seguía tecleando)
        self.sim_pos = None              # última posición que el simulador dio al cursor (según el gancho)
        self.sim_sent = collections.deque()  # (t, (x, y)) anotados por el simulador ANTES de SendInput
        self.sim_sent_used = 0.0         # el último anotado que ya explicó un salto (cada uno explica uno solo)
        self.sim_announced = 0
        self.displaced = False           # un acto ajeno sacó el cursor de sim_pos y todavía no volvió
        self.cursor_returns = []         # vueltas a sim_pos tras un salto ajeno: restauraciones, no movimientos
        self.pending_late = []           # ráfagas evaluadas sin restaurar que aún pueden restaurarse tarde
        self.delivered = []              # caracteres que el gancho dejó pasar a su ventana
        self.typed = 0
        self.swallowed = 0               # tragados con la ventana robada (cuentan como perdidos)
        self.swallowed_excluded = 0      # tragados con la ventana quitada por el dueño o sin frente al iniciar
        self.sim_mouse_swallowed = 0
        self.paused_for_owner = 0
        # medición
        self.t_start = None
        self.t_end = None
        self.start_source = None
        self.start_front = None
        self.fg_ours = False
        self.fg_current = None           # ventana delantera vista por última vez (WinEvent o sondeo)
        self.fg_null_since = None
        self.away_cause = None           # None | 'robo' | 'dueno' | 'inicio'
        self.fg_log = []
        self.fg_left = {}                # hwnd -> instante en que dejó de estar delante
        self.thefts = []                 # {ini, fin, hwnd, titulo, proceso}
        self.acts = []                   # actos ajenos
        self.bursts = []
        self.open_burst = None
        self.counts = collections.Counter()
        self.points = collections.deque()  # (t, x, y) de movimientos enganchados: explican lo que ve el sondeo
        self.owner_points = collections.deque()  # (t, (x, y)) de movimientos reales del dueño (subconjunto de points)
        self.closing_requests = 0
        self.final = {}
        self.text = None
        self.prev_fg = None
        self.stop_sim = threading.Event()
        # referencias vivas de los callbacks ctypes
        self._kb = w32.HOOKPROC(self._kb_hook)
        self._ms = w32.HOOKPROC(self._ms_hook)
        self._we = w32.WINEVENTPROC(self._fg_event)
        self._wp = w32.WNDPROC(self._wndproc)

    # ---------- utilidades de estado ----------
    def measuring(self, t):
        return self.t_start is not None and t >= self.t_start and (self.t_end is None or t <= self.t_end)

    def _owner(self, t):
        self.owner_last = t
        if self.measuring(t):
            self.owner_events += 1
        if self.owner_intervals and t - self.owner_intervals[-1][1] <= OWNER_GRACE_S:
            self.owner_intervals[-1][1] = t
        else:
            self.owner_intervals.append([t, t])

    def _front_ours(self):
        return user32.GetForegroundWindow() == self.hwnd

    def _cursor_now(self):
        return w32.cursor()

    def _at_sim(self, pt):
        return near(pt, self.sim_pos)

    def _in_pause(self, t):
        last = max(x for x in (self.sim_last, self.owner_last, self.t_start, 0.0) if x is not None)
        return t - last >= PAUSE_RULE_S

    def _act(self, t, kind, source, **detail):
        """Un acto ajeno dentro de la medición: entra en la ráfaga abierta y se clasifica por pausa."""
        if not self.measuring(t):
            self.counts["fuera_de_medicion_" + kind] += 1
            return
        a = {"t": round(t, 3), "tipo": kind, "fuente": source, "en_pausa": self._in_pause(t)}
        a.update(detail)
        self.acts.append(a)
        self.counts[kind + "_" + source] += 1
        if kind in NOT_IN_BURSTS:
            return
        if self.open_burst is None:
            self.open_burst = {"ini": round(t, 3), "actos": 0, "tipos": collections.Counter(), "en_pausa": True}
        self.open_burst["actos"] += 1
        self.open_burst["tipos"][kind] += 1
        if not a["en_pausa"]:
            self.open_burst["en_pausa"] = False
        self.open_burst["fin"] = round(t, 3)

    def _close_burst(self, t, why):
        b = self.open_burst
        if b is None:
            return
        self.open_burst = None
        fg = self._front_ours()
        at_pos = self._at_sim(self._cursor_now())
        b.update({"evaluada": round(t, 3), "por": why, "frente_usuario": fg, "cursor_usuario": at_pos,
                  "restaurada": bool(fg and at_pos), "tipos": dict(b["tipos"])})
        if not b["restaurada"]:
            # Si después vuelven frente y cursor sin que el usuario los recupere, la ráfaga se restauró tarde.
            b["restaurada_tarde"] = False
            self.pending_late.append(b)
        self.bursts.append(b)

    def _owner_between(self, a, b):
        """El dueño dio input real entre `a` y `b` (con el margen OWNER_GRACE_S tras su último input)."""
        return any(s <= b and e + OWNER_GRACE_S >= a for s, e in self.owner_intervals)

    def _check_late(self, t, cursor=None):
        """Frente y cursor del usuario de vuelta: las ráfagas que se evaluaron sin restaurar quedan restauradas tarde,
        con el retraso desde su evaluación. `cursor`: la posición ya conocida (en un gancho de bajo nivel el cursor
        todavía no se movió). Si el dueño dio input desde que empezó la ráfaga, la vuelta pudo ser suya (devolvió el
        cursor a mano, clicó su ventana): no se acredita a BAXY y la ráfaga deja de esperar."""
        if self.pending_late:
            mine = [b for b in self.pending_late if self._owner_between(b["ini"], t)]
            for b in mine:
                b["recuperada_por_dueno"] = True
            if mine:
                self.counts["rafaga_recuperada_por_dueno"] += len(mine)
                self.pending_late = [b for b in self.pending_late if not b.get("recuperada_por_dueno")]
        if not self.pending_late or not self._front_ours():
            return
        if not self._at_sim(cursor if cursor is not None else self._cursor_now()):
            return
        for b in self.pending_late:
            b["restaurada_tarde"] = True
            b["retraso_ms"] = int(round((t - b["evaluada"]) * 1000))
        self.pending_late = []

    def _cursor_back(self, t, pt):
        """El cursor volvió a sim_pos tras un salto ajeno: restauración (dentro de la ráfaga abierta, o tarde)."""
        self.displaced = False
        if not self.measuring(t):
            return
        in_burst = self.open_burst is not None
        self.cursor_returns.append({"t": round(t, 3), "en_rafaga": in_burst})
        self.counts["cursor_vuelto_en_rafaga" if in_burst else "cursor_vuelto_tras_rafaga"] += 1
        if in_burst:
            self.open_burst["cursor_vuelto"] = round(t, 3)
        else:
            self._check_late(t, pt)

    def _foreign_cursor(self, t, pt, kind, source, **detail):
        """Movimiento ajeno del cursor (enganchado o visto por el sondeo): una vuelta a sim_pos tras un salto ajeno
        es restauración; lo demás es un acto."""
        if self.displaced and self._at_sim(pt):
            self._cursor_back(t, pt)
            return "vuelta"
        if self.sim_pos is not None:
            self.displaced = True
        self._act(t, kind, source, **detail)
        return "acto"

    def _sim_moved(self):
        """El simulador movió el cursor: el usuario lo recuperó él mismo; lo pendiente ya no se restaura tarde."""
        self.displaced = False
        self.pending_late = []

    def _cursor_jump(self, t, prev_t, prev, p):
        """Un salto que vio el sondeo (con el candado tomado). Devuelve «simulador», «vuelta», «explicado» o «acto»."""
        while self.points and t - self.points[0][0] > 1.0:
            self.points.popleft()
        while self.owner_points and t - self.owner_points[0][0] > 1.0:
            self.owner_points.popleft()
        while self.sim_sent and t - self.sim_sent[0][0] > SENT_TTL_S:
            self.sim_sent.popleft()
        # 1) Un punto que el simulador anotó antes de mandarlo y que todavía no explicó otro salto.
        match = None
        for ts, q in self.sim_sent:
            if ts > self.sim_sent_used and near(p, q):
                match = ts
        if match is not None:
            self.sim_sent_used = match
            self._check_late(t, prev)  # si el gancho llega tarde: ¿estaba ya todo de vuelta antes de este movimiento?
            self._sim_moved()
            return "simulador"
        # 2) El dueño movió el cursor ahí (movimiento real enganchado desde la muestra anterior): nunca es una
        # restauración de BAXY, aunque lo devuelva a su sitio; ese desplazamiento ya no está pendiente.
        if any(tq >= prev_t - 0.05 and near(p, q) for tq, q in self.owner_points):
            if self.displaced and self._at_sim(p):
                self.displaced = False
                self.counts["cursor_vuelto_por_dueno"] += 1
                self._check_late(t, p)
            return "explicado"
        # 3) La vuelta a la posición del usuario tras un salto ajeno.
        if self.displaced and self._at_sim(p):
            self._cursor_back(t, p)
            return "vuelta"
        # 4) Un movimiento enganchado desde la muestra anterior (50 ms de holgura: el gancho corre antes de que el
        # cursor se mueva); un punto viejo no explica volver a él.
        if any(tq >= prev_t - 0.05 and near(p, q) for tq, q in self.points):
            return "explicado"
        # 5) Salto sin movimiento enganchado ni anotado: SetCursorPos (BAXY hoy lo usa sin marca).
        return self._foreign_cursor(t, p, "cursor_saltado", "ajeno", desde=list(prev), hasta=list(p))

    # ---------- ganchos ----------
    def _kb_hook(self, code, wparam, lparam):
        try:
            if code == w32.HC_ACTION:
                k = w32.KBDLLHOOKSTRUCT.from_address(lparam)
                t = time.time()
                down = wparam in (w32.WM_KEYDOWN, w32.WM_SYSKEYDOWN)
                with self.lock:
                    if not k.flags & w32.LLKHF_INJECTED:
                        self._owner(t)
                    elif k.dwExtraInfo == w32.SIM_MARK:
                        self.sim_last = t
                        if user32.GetForegroundWindow() != self.hwnd:
                            if down:
                                if self.away_cause in ("dueno", "inicio"):
                                    self.swallowed_excluded += 1
                                else:
                                    self.swallowed += 1
                            return 1
                        if down and k.vkCode == w32.VK_PACKET:
                            self.delivered.append(chr(k.scanCode))
                    elif down:
                        source = key_source(k.dwExtraInfo, k.vkCode)
                        if user32.GetForegroundWindow() == self.hwnd:
                            ch = chr(k.scanCode) if k.vkCode == w32.VK_PACKET else None
                            self._act(t, "tecla_en_ventana_usuario", source, vk=k.vkCode, car=ch)
                        else:
                            self._act(t, "tecla_otra_ventana", source)
        except Exception as e:  # noqa: BLE001 — un fallo nunca bloquea el teclado del dueño
            self.counts["error_gancho"] += 1
            self.counts["error_" + type(e).__name__] += 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _ms_hook(self, code, wparam, lparam):
        try:
            if code == w32.HC_ACTION:
                m = w32.MSLLHOOKSTRUCT.from_address(lparam)
                t = time.time()
                pt = (m.pt.x, m.pt.y)
                move = wparam == w32.WM_MOUSEMOVE
                with self.lock:
                    if not m.flags & w32.LLMHF_INJECTED:
                        self._owner(t)
                        if move:
                            self.points.append((t, pt))
                            self.owner_points.append((t, pt))
                    elif m.dwExtraInfo == w32.SIM_MARK:
                        if move and user32.GetForegroundWindow() != self.hwnd:
                            self.sim_mouse_swallowed += 1
                            return 1
                        self.sim_last = t
                        if move:
                            # El gancho corre antes de que el cursor se mueva: lo restaurado tarde se mira con la
                            # posición anterior del usuario, y después el simulador la recupera él mismo.
                            self._check_late(t)
                            self.sim_pos = pt
                            self.points.append((t, pt))
                            self._sim_moved()
                    else:
                        source = "baxy" if m.dwExtraInfo == w32.BAXY_MARK else "ajeno"
                        if move:
                            self.points.append((t, pt))
                            self._foreign_cursor(t, pt, "raton_movido", source, x=pt[0], y=pt[1])
                        elif wparam in (w32.WM_LBUTTONDOWN, w32.WM_RBUTTONDOWN, w32.WM_MBUTTONDOWN,
                                        w32.WM_XBUTTONDOWN):
                            in_user = w32.root_at(pt) == self.hwnd
                            self._act(t, "clic", source, x=pt[0], y=pt[1], en_ventana_usuario=in_user)
                        elif wparam in (w32.WM_MOUSEWHEEL, w32.WM_MOUSEHWHEEL):
                            self._act(t, "rueda", source, x=pt[0], y=pt[1])
        except Exception as e:  # noqa: BLE001
            self.counts["error_gancho"] += 1
            self.counts["error_" + type(e).__name__] += 1
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _fg_event(self, _hook, _event, hwnd, id_object, _id_child, _tid, _ms):
        try:
            if id_object == 0 and hwnd:
                self._fg_change(user32.GetAncestor(hwnd, w32.GA_ROOT) or hwnd, "evento")
        except Exception as e:  # noqa: BLE001
            self.counts["error_winevent_" + type(e).__name__] += 1

    def _fg_change(self, root, via):
        """Transición de primer plano, venga del WinEvent o del sondeo (que también ve el primer plano vacío y lo que
        el WinEvent no avisa). Se ignora si no cambia la ventana delantera."""
        root = int(root or 0)
        if root == self.fg_current:
            return
        t = time.time()
        ours = root == self.hwnd
        pid = w32.window_pid(root)[0] if root else 0
        entry = {"t": round(t, 3), "hwnd": root, "titulo": w32.title(root)[:120] if root else "(ninguna)",
                 "proceso": w32.process_name(pid) if pid else None, "pid": pid, "usuario": ours, "via": via}
        with self.lock:
            if root == self.fg_current:
                return
            now_fg = user32.GetForegroundWindow()
            if int(user32.GetAncestor(now_fg, w32.GA_ROOT) or now_fg or 0) != root:
                # Aviso viejo (un WinEvent llega encolado, o el sondeo leyó antes de otro cambio): el estado lo decide
                # el primer plano real; el destello se anota pero no cambia el estado.
                if self.measuring(t):
                    entry["transitorio"] = True
                    entry["clase"] = transient_kind(root, t, self.fg_left)
                    self.fg_log.append(entry)
                    self.counts["primer_plano_transitorio"] += 1
                    self.counts["primer_plano_" + entry["clase"]] += 1
                return
            if self.fg_current is not None:
                self.fg_left[self.fg_current] = t
            self.fg_current = root
            if self.measuring(t):
                self.fg_log.append(entry)
                if self.fg_ours and not ours:
                    owner_recent = self.owner_last is not None and t - self.owner_last <= OWNER_GRACE_S
                    if owner_recent:
                        self.away_cause = "dueno"
                        entry["causa"] = "dueno"
                    else:
                        self.away_cause = "robo"
                        entry["causa"] = "robo"
                        self.thefts.append({"ini": round(t, 3), "fin": None, "hwnd": entry["hwnd"],
                                            "titulo": entry["titulo"], "proceso": entry["proceso"]})
                        self._act(t, "robo_foco", "ajeno", titulo=entry["titulo"], proceso=entry["proceso"])
                elif ours and not self.fg_ours:
                    if self.thefts and self.thefts[-1]["fin"] is None:
                        self.thefts[-1]["fin"] = round(t, 3)
                    self.away_cause = None
                    self._check_late(t)
                elif not ours and self.away_cause == "robo":
                    # BAXY pasó de una ventana suya a otra mientras el usuario sigue sin la suya.
                    self._act(t, "cambio_foco_ajeno", "ajeno", titulo=entry["titulo"], proceso=entry["proceso"])
            self.fg_ours = ours

    def install_hooks(self):
        self.t_hooks = time.time()
        for kind, proc in ((w32.WH_KEYBOARD_LL, self._kb), (w32.WH_MOUSE_LL, self._ms)):
            h = user32.SetWindowsHookExW(kind, proc, self.hinst, 0)
            if not h:
                raise OSError(f"SetWindowsHookExW({kind}) falló: {ctypes.get_last_error()}")
            self.hooks.append(h)
        self.winevent = user32.SetWinEventHook(w32.EVENT_SYSTEM_FOREGROUND, w32.EVENT_SYSTEM_FOREGROUND, None,
                                               self._we, 0, 0, w32.WINEVENT_OUTOFCONTEXT)

    def remove_hooks(self):
        for h in self.hooks:
            user32.UnhookWindowsHookEx(h)
        self.hooks = []
        if self.winevent:
            user32.UnhookWinEvent(self.winevent)
            self.winevent = None

    # ---------- ventana ----------
    def create_window(self):
        wc = w32.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = self._wp
        wc.hInstance = self.hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(w32.IDC_ARROW))
        wc.hbrBackground = user32.GetSysColorBrush(w32.COLOR_WINDOW)
        wc.lpszClassName = CLASS
        user32.RegisterClassExW(ctypes.byref(wc))
        try:
            scale = user32.GetDpiForSystem() / 96.0
        except (AttributeError, OSError):
            scale = 1.0
        w, h = int(460 * scale), int(240 * scale)
        wa = w32.work_area()
        x, y = wa[0] + int(8 * scale), wa[3] - h - int(8 * scale)  # esquina inferior izquierda del área de trabajo
        self.hwnd = user32.CreateWindowExW(0, CLASS, TITLE, w32.WS_OVERLAPPEDWINDOW, x, y, w, h,
                                           None, None, self.hinst, None)
        if not self.hwnd:
            raise OSError(f"CreateWindowExW falló: {ctypes.get_last_error()}")
        cr = wt.RECT()
        user32.GetClientRect(self.hwnd, ctypes.byref(cr))
        self.edit = user32.CreateWindowExW(0, "EDIT", "", w32.WS_CHILD | w32.WS_VISIBLE | w32.WS_VSCROLL
                                           | w32.ES_MULTILINE | w32.ES_AUTOVSCROLL, 0, 0, cr.right, cr.bottom,
                                           self.hwnd, None, self.hinst, None)
        user32.SendMessageW(self.edit, w32.WM_SETFONT, w32.gdi32.GetStockObject(w32.DEFAULT_GUI_FONT), 1)
        user32.SendMessageW(self.edit, w32.EM_LIMITTEXT, 0, 0)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == w32.WM_SIZE and self.edit:
                user32.MoveWindow(self.edit, 0, 0, lparam & 0xFFFF, (lparam >> 16) & 0xFFFF, True)
                return 0
            if msg == w32.WM_SETFOCUS and self.edit:
                user32.SetFocus(self.edit)
                return 0
            if msg == w32.WM_CLOSE:
                # Nadie salvo el propio medidor cierra la ventana del usuario: si alguien lo pide, se anota.
                with self.lock:
                    self.closing_requests += 1
                    self._act(time.time(), "cierre_pedido", "ajeno")
                return 0
            if msg == WM_APP_SHOW:
                user32.ShowWindow(hwnd, w32.SW_SHOWNORMAL)
                user32.UpdateWindow(hwnd)
                ok = w32.bring_front(hwnd)
                user32.SetFocus(self.edit)
                return 1 if ok else 0
            if msg == WM_APP_FRONT:
                ok = w32.bring_front(hwnd)
                user32.SetFocus(self.edit)
                return 1 if ok else 0
            if msg == WM_APP_FINISH:
                self.remove_hooks()
                n = user32.SendMessageW(self.edit, w32.WM_GETTEXTLENGTH, 0, 0)
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.SendMessageW(self.edit, w32.WM_GETTEXT, n + 1, ctypes.addressof(buf))
                self.text = buf.value
                was_front = user32.GetForegroundWindow() == hwnd
                user32.DestroyWindow(hwnd)
                if was_front and self.prev_fg and user32.IsWindow(self.prev_fg) and user32.IsWindowVisible(self.prev_fg):
                    w32.bring_front(self.prev_fg, show=False)  # devuelve el frente a quien lo tenía antes de medir
                user32.PostQuitMessage(0)
                return 0
        except Exception as e:  # noqa: BLE001
            self.counts["error_ventana_" + type(e).__name__] += 1
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def pump(self):
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ---------- hilos ----------
    def wait_owner_pause(self, pause_s, max_s):
        """Espera a que el input REAL lleve pause_s sin aparecer (contando desde que se instalaron los ganchos)."""
        deadline = time.time() + max_s
        while time.time() < deadline:
            with self.lock:
                last = max(self.owner_last or 0.0, self.t_hooks)
            if time.time() - last >= pause_s:
                return True
            time.sleep(0.05)
        return False

    def simulator(self):
        t0 = self.t_start
        per_cycle = int(TYPE_S * CPS)
        cycle = TYPE_S + PAUSE_S
        cr = wt.RECT()
        user32.GetClientRect(self.edit, ctypes.byref(cr))
        org = wt.POINT(0, 0)
        user32.ClientToScreen(self.edit, ctypes.byref(org))
        cx, cy = org.x + cr.right // 2, org.y + cr.bottom // 2
        rx, ry = max(8, cr.right // 4), max(6, cr.bottom // 4)
        idx = 0
        slot = 0
        if getattr(self.args, "solo_raton", False):
            # molestia-ayudantes: la persona sólo mueve el ratón dentro de su ventana, sin teclas, aunque otra ventana
            # tenga el frente (un movimiento suelto no alcanza a ninguna ventana: no debe cortar a BAXY). Revisión r2:
            # tramos de TYPE_S moviendo y RATON_REST_S con la mano quieta; BAXY espera ese descanso para empezar (nunca
            # salta el cursor bajo una mano que lo mueve) y el movimiento que vuelve a mitad de su guion no lo corta.
            while not self.stop_sim.wait(1.0 / CPS):
                idx += 1
                if idx % int(TYPE_S * CPS) == 0 and self.stop_sim.wait(RATON_REST_S):
                    break
                ang = (idx % 24) / 24.0 * 6.283185307
                x, y = int(cx + rx * math.cos(ang)), int(cy + ry * math.sin(ang))
                with self.lock:
                    self.sim_sent.append((time.time(), (x, y)))
                    self.sim_announced += 1
                w32.send_move(x, y, w32.SIM_MARK)
            return
        while not self.stop_sim.is_set():
            c, i = divmod(slot, per_cycle)
            due = t0 + c * cycle + i / CPS
            now = time.time()
            if due < now - 1.0 / CPS:  # atrasado (p. ej. pausado por el dueño): salta al hueco vigente
                slot += 1
                continue
            if self.stop_sim.wait(max(0.0, due - now)):
                break
            slot += 1
            with self.lock:
                owner_busy = self.owner_last is not None and time.time() - self.owner_last < OWNER_GRACE_S + 0.5
                if owner_busy:
                    self.paused_for_owner += 1
                    continue
                # Antes de volver a teclear se evalúa si la ráfaga ajena dejó ventana y cursor como estaban.
                self._close_burst(time.time(), "simulador_vuelve")
                front = user32.GetForegroundWindow() == self.hwnd
            ch = TEXT[idx % len(TEXT)]
            idx += 1
            self.typed += 1
            w32.send_char(ch, w32.SIM_MARK)
            if front:
                ang = (idx % 24) / 24.0 * 6.283185307
                x, y = int(cx + rx * math.cos(ang)), int(cy + ry * math.sin(ang))
                with self.lock:  # anotado ANTES de SendInput: el sondeo puede ver el cursor antes que el gancho
                    self.sim_sent.append((time.time(), (x, y)))
                    self.sim_announced += 1
                w32.send_move(x, y, w32.SIM_MARK)

    def poller(self):
        """Cada 10 ms: primer plano (respaldo del WinEvent) y saltos del cursor que ningún gancho explica."""
        prev = w32.cursor()
        prev_t = time.time()
        while not self.stop_sim.is_set():
            time.sleep(POLL_S)
            fg = user32.GetForegroundWindow()
            if fg:
                self.fg_null_since = None
                root = user32.GetAncestor(fg, w32.GA_ROOT) or fg
                if root != self.fg_current:
                    self._fg_change(root, "sondeo")
            elif self.fg_current:
                # Primer plano vacío: cuenta si dura 50 ms (en un cambio de ventana normal dura menos).
                self.fg_null_since = self.fg_null_since or time.time()
                if time.time() - self.fg_null_since >= 0.05:
                    self._fg_change(0, "sondeo")
            p = w32.cursor()
            t = time.time()
            if p == prev:
                prev_t = t
                continue
            with self.lock:
                self._cursor_jump(t, prev_t, prev, p)
            prev, prev_t = p, t

    def control(self):
        try:
            self._control()
        except Exception as e:  # noqa: BLE001
            self.counts["error_control_" + type(e).__name__] += 1
            self.final["error"] = repr(e)
        finally:
            self.stop_sim.set()
            if self.hwnd:
                user32.SendMessageW(self.hwnd, WM_APP_FINISH, 0, 0)
            else:
                user32.PostThreadMessageW(self.ui_tid, w32.WM_QUIT, 0, 0)

    def _stop_requested(self):
        return os.path.exists(os.path.join(self.args.control, "parar"))

    def _write_control(self, name, data):
        with open(os.path.join(self.args.control, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f)

    def _control(self):
        a = self.args
        t_launch = time.time()
        if not self.wait_owner_pause(a.pausa, a.espera_max):
            self.final["abortado"] = "dueno_ocupado"
            return
        self.prev_fg = user32.GetForegroundWindow()
        shown = user32.SendMessageW(self.hwnd, WM_APP_SHOW, 0, 0)
        self._write_control("listo.json", {"pid": os.getpid(), "hwnd": int(self.hwnd), "t": time.time(),
                                           "frente": bool(shown)})
        deadline = t_launch + a.max_s
        # Señal de inicio.
        events = a.inicio[len("eventos:"):] if a.inicio.startswith("eventos:") else None
        while events:
            if self._stop_requested() or time.time() > deadline:
                self.final["sin_inicio"] = True
                return
            try:
                if os.path.getmtime(events) >= t_launch:
                    with open(events, encoding="utf-8-sig", errors="replace") as f:
                        if '"type":"runtime"' in f.read():
                            break
            except OSError:
                pass
            time.sleep(0.05)
        self.start_source = "eventos" if events else "ahora"
        # La App ya arrancó: la ventana del usuario recupera el frente (tras una pausa breve del dueño).
        self.wait_owner_pause(a.pausa, 30)
        front = False
        for _ in range(3):
            front = bool(user32.SendMessageW(self.hwnd, WM_APP_FRONT, 0, 0))
            if front:
                break
            time.sleep(0.2)
        with self.lock:
            self.t_start = time.time()
            self.sim_last = self.t_start
            self.start_front = front
            fg = user32.GetForegroundWindow()
            self.fg_current = int(user32.GetAncestor(fg, w32.GA_ROOT) or fg or 0)
            self.fg_ours = self.fg_current == self.hwnd
            self.away_cause = None if self.fg_ours else "inicio"
        self._write_control("midiendo.json", {"t0": self.t_start, "cps": CPS, "escribe_s": TYPE_S,
                                              "pausa_s": PAUSE_S, "hwnd": int(self.hwnd), "frente": front})
        sim = threading.Thread(target=self.simulator, daemon=True)
        poll = threading.Thread(target=self.poller, daemon=True)
        sim.start()
        poll.start()
        while not self._stop_requested():
            if time.time() > deadline:
                self.final["sin_senal_de_parada"] = True
                break
            time.sleep(0.05)
        t_stop = time.time()
        time.sleep(TAIL_S)
        with self.lock:
            self.t_end = time.time()
        self.stop_sim.set()
        sim.join(2)
        poll.join(2)
        time.sleep(FINAL_WAIT_S)
        with self.lock:
            now = time.time()
            for th in self.thefts:
                if th["fin"] is None:
                    th["abierto_al_final"] = True
            self._close_burst(now, "final")
            self._check_late(now)
            cur = w32.cursor()
            r = w32.rect(self.hwnd)
            self.final.update({
                "t_parada": round(t_stop, 3),
                "frente_usuario": user32.GetForegroundWindow() == self.hwnd,
                "cursor_en_ventana": w32.inside(cur, r),
                "cursor_en_su_posicion": self.sim_pos is not None
                and abs(cur[0] - self.sim_pos[0]) <= CURSOR_TOL and abs(cur[1] - self.sim_pos[1]) <= CURSOR_TOL,
                "cursor": list(cur), "posicion_usuario": list(self.sim_pos) if self.sim_pos else None,
            })

    # ---------- informe ----------
    def excluded(self, t):
        return any(s <= t <= e + OWNER_GRACE_S for s, e in self.owner_intervals)

    def report(self, avisos):
        delivered = "".join(self.delivered)
        text = self.text or ""
        # Teclas del simulador que el gancho nunca vio: ni entregadas ni tragadas (ni excluidas por el dueño).
        unseen = max(0, self.typed - len(delivered) - self.swallowed - self.swallowed_excluded)
        lost_edit, inserted, recovered = text_loss(delivered, text, typed_text(self.typed), unseen)
        acts = [a for a in self.acts if not self.excluded(a["t"])]
        excl = len(self.acts) - len(acts)
        end = self.t_end or time.time()
        thefts = [th for th in self.thefts if not self.excluded(th["ini"])]
        stolen_ms = sum(int(((th["fin"] or end) - th["ini"]) * 1000) for th in thefts)
        bursts = [b for b in self.bursts if not self.excluded(b["ini"])]
        kinds = collections.Counter((a["tipo"], a["fuente"]) for a in acts)

        def n(kind, src=None):
            return sum(v for (k, s), v in kinds.items() if k == kind and (src is None or s == src))
        owner_active = any(e >= (self.t_start or 0) - OWNER_GRACE_S and s <= end for s, e in self.owner_intervals)
        r = {
            "medido": self.t_start is not None,
            "inicio": self.start_source, "t_inicio": self.t_start, "t_fin": self.t_end,
            "duracion_s": round(end - self.t_start, 2) if self.t_start else 0,
            "frente_al_iniciar": self.start_front,
            "perdidos": self.swallowed + lost_edit,
            "perdidos_tragados": self.swallowed,
            "perdidos_en_texto": lost_edit,
            "insertados": inserted,
            "entregados_sin_gancho": recovered,
            "teclas_baxy_en_ventana_usuario": n("tecla_en_ventana_usuario"),
            "teclas_baxy_en_ventana_usuario_marca_baxy": n("tecla_en_ventana_usuario", "baxy"),
            "teclas_baxy_en_ventana_usuario_uia": n("tecla_en_ventana_usuario", "uia"),
            "teclas_otra_ventana": n("tecla_otra_ventana"),
            "teclas_uia": n("tecla_en_ventana_usuario", "uia") + n("tecla_otra_ventana", "uia"),
            "robos_foco": len(thefts),
            "ms_robados": stolen_ms,
            "cambios_foco_ajenos": n("cambio_foco_ajeno"),
            "movimientos_cursor": n("raton_movido") + n("cursor_saltado"),
            "cursor_saltado": n("cursor_saltado"),
            "raton_movido_inyectado": n("raton_movido"),
            "clics": n("clic"),
            "clics_en_ventana_usuario": sum(1 for a in acts if a["tipo"] == "clic" and a.get("en_ventana_usuario")),
            "rueda": n("rueda"),
            "cierres_pedidos": n("cierre_pedido"),
            "actos": len(acts),
            "actos_fuera_de_pausa": sum(1 for a in acts if not a["en_pausa"]),
            "actos_en_pausa": sum(1 for a in acts if a["en_pausa"]),
            "rafagas": len(bursts),
            "rafagas_restauradas": sum(1 for b in bursts if b["restaurada"]),
            "rafagas_restauradas_tarde": sum(1 for b in bursts if b.get("restaurada_tarde")),
            "retrasos_restauracion_tarde_ms": sorted(b["retraso_ms"] for b in bursts if b.get("restaurada_tarde")),
            "rafagas_recuperadas_por_dueno": sum(1 for b in bursts if b.get("recuperada_por_dueno")),
            "cursor_vueltas_restauradas": sum(1 for c in self.cursor_returns if not self.excluded(c["t"])),
            "primer_plano_transitorios": sum(1 for e in self.fg_log if e.get("transitorio")),
            "primer_plano_sin_frente": sum(1 for e in self.fg_log if e.get("clase") == "sin_frente"),
            "primer_plano_aviso_tardio": sum(1 for e in self.fg_log if e.get("clase") == "aviso_tardio"),
            "dueno_activo": owner_active,
            "eventos_dueno": self.owner_events,
            "actos_excluidos_por_dueno": excl,
            "tragados_excluidos": self.swallowed_excluded,
            "simulador": {"tecleados": self.typed, "entregados": len(delivered), "no_vistos_por_gancho": unseen,
                          "pausados_por_dueno":
                          self.paused_for_owner, "raton_tragado": self.sim_mouse_swallowed,
                          "movimientos_anotados": self.sim_announced},
            "final": self.final,
            "avisos": avisos,
            "contadores": dict(self.counts),
            "intervalos_dueno": [[round(s, 3), round(e, 3)] for s, e in self.owner_intervals
                                 if self.t_start and e >= self.t_start - OWNER_GRACE_S],
            "primer_plano": self.fg_log,
            "robos": self.thefts,
            "rafagas_detalle": self.bursts,
            "cursor_vueltas": self.cursor_returns,
            "actos_detalle": self.acts[:MAX_LOGGED_ACTS],
            "actos_detalle_truncado": len(self.acts) > MAX_LOGGED_ACTS,
            "texto_entregado": delivered,
            "texto_ventana": text,
        }
        r["pct_restauradas"] = round(100.0 * r["rafagas_restauradas"] / r["rafagas"], 1) if r["rafagas"] else None
        r["resumen"] = summary_line(r)
        return r


def summary_line(r):
    if r.get("final", {}).get("abortado"):
        return f"molestia: ABORTADO ({r['final']['abortado']})"
    if not r.get("medido"):
        return "molestia: SIN MEDICIÓN (no llegó la señal de inicio)"
    f = r.get("final", {})
    yn = {True: "si", False: "no", None: "?"}
    rest = f"{r['rafagas_restauradas']}/{r['rafagas']}"
    s = (f"molestia: perdidos={r['perdidos']} insertados={r['insertados']} "
         f"teclas_baxy={r['teclas_baxy_en_ventana_usuario']} uia={r.get('teclas_uia', 0)} "
         f"robos={r['robos_foco']} ms_robados={r['ms_robados']} "
         f"cursor={r['movimientos_cursor']} vueltas={r.get('cursor_vueltas_restauradas', 0)} clics={r['clics']} "
         f"fuera_pausa={r['actos_fuera_de_pausa']} restauradas={rest} tarde={r.get('rafagas_restauradas_tarde', 0)} "
         f"transitorios={r.get('primer_plano_transitorios', 0)} final_frente={yn[f.get('frente_usuario')]} "
         f"final_cursor={yn[f.get('cursor_en_su_posicion')]} dueno={'ACTIVO' if r['dueno_activo'] else 'no'}")
    if r.get("avisos"):  # familias de input remoto sin marca: lo que inyecten se atribuiría a BAXY
        s += " avisos=input_remoto:" + ",".join(sorted({p for p in REMOTE_INPUT for a in r["avisos"]
                                                        if a.startswith(p)} or set(r["avisos"])))
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="modo", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--control", required=True)
    m.add_argument("--salida", required=True)
    m.add_argument("--inicio", default="ahora")
    m.add_argument("--pausa", type=float, default=2.0, help="pausa del dueño (s) antes de mostrar la ventana")
    m.add_argument("--espera-max", type=float, default=1200.0)
    m.add_argument("--max-s", type=float, default=900.0)
    m.add_argument("--solo-raton", action="store_true",
                   help="el usuario simulado sólo mueve el ratón en su ventana, sin teclear (2 s moviendo, 0,7 s quieto)")
    e = sub.add_parser("espera")
    e.add_argument("--pausa", type=float, default=2.0)
    e.add_argument("--espera-max", type=float, default=1200.0)
    a = ap.parse_args()
    w32.dpi_aware()
    med = Medidor(a)
    med.ui_tid = kernel32.GetCurrentThreadId()
    if a.modo == "espera":
        med.install_hooks()

        def waiter():
            ok = med.wait_owner_pause(a.pausa, a.espera_max)
            med.final["ok"] = ok
            user32.PostThreadMessageW(med.ui_tid, w32.WM_QUIT, 0, 0)
        threading.Thread(target=waiter, daemon=True).start()
        med.pump()
        med.remove_hooks()
        print(json.dumps({"pausa_dueno": med.final.get("ok"), "pausa_s": a.pausa}))
        return 0 if med.final.get("ok") else 4
    os.makedirs(a.control, exist_ok=True)
    avisos = remote_input_processes()
    med.create_window()
    med.install_hooks()
    threading.Thread(target=med.control, daemon=True).start()
    med.pump()
    med.remove_hooks()
    r = med.report(avisos)
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    with open(a.salida, "w", encoding="utf-8", newline="\n") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(r["resumen"])
    return 4 if r["final"].get("abortado") else 0


if __name__ == "__main__":
    sys.exit(main())
