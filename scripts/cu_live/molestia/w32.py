"""Declaraciones Win32 por ctypes que comparten el medidor de molestia y su autoprueba.

Sólo user32/kernel32 de Windows, sin dependencias. Todas las coordenadas son de pantalla en píxeles físicos:
el proceso se declara consciente de DPI por monitor antes de crear nada (dpi_aware), igual que los clics del
producto (VisibleControlSurface.InPhysicalPixels).
"""
import ctypes
from ctypes import wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

# Marcas en dwExtraInfo. La del simulador la elige este arnés; la de BAXY es la del producto («BAXY»,
# BaxyInputMark.cs; UserInputPauseTests.TheAnnoyanceMeterReadsTheProductsMark las mantiene iguales).
SIM_MARK = 0x5349_4D55  # 'SIMU'
BAXY_MARK = 0x4241_5859  # 'BAXY'

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
LLKHF_INJECTED = 0x10
LLKHF_LOWER_IL_INJECTED = 0x02
LLMHF_INJECTED = 0x01
LLMHF_LOWER_IL_INJECTED = 0x02

WM_DESTROY = 0x0002
WM_SIZE = 0x0005
WM_SETFOCUS = 0x0007
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_SETFONT = 0x0030
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_MOUSEHWHEEL = 0x020E
WM_APP = 0x8000
EM_LIMITTEXT = 0x00C5

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
VK_PACKET = 0xE7

WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_VSCROLL = 0x00200000
WS_BORDER = 0x00800000
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
SW_SHOWNORMAL = 1
SW_SHOW = 5
SW_RESTORE = 9
GA_ROOT = 2
SPI_GETWORKAREA = 0x0030
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DEFAULT_GUI_FONT = 17
IDC_ARROW = 32512
COLOR_WINDOW = 5


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


def _sig(fn, res, *args):
    fn.restype = res
    fn.argtypes = list(args)
    return fn


_sig(user32.SetWindowsHookExW, wt.HHOOK, ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD)
_sig(user32.CallNextHookEx, LRESULT, wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_sig(user32.UnhookWindowsHookEx, wt.BOOL, wt.HHOOK)
_sig(user32.SetWinEventHook, wt.HANDLE, wt.DWORD, wt.DWORD, wt.HMODULE, WINEVENTPROC, wt.DWORD, wt.DWORD, wt.DWORD)
_sig(user32.UnhookWinEvent, wt.BOOL, wt.HANDLE)
_sig(user32.GetMessageW, wt.BOOL, ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
_sig(user32.PeekMessageW, wt.BOOL, ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT)
_sig(user32.TranslateMessage, wt.BOOL, ctypes.POINTER(wt.MSG))
_sig(user32.DispatchMessageW, LRESULT, ctypes.POINTER(wt.MSG))
_sig(user32.PostMessageW, wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_sig(user32.SendMessageW, LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_sig(user32.PostThreadMessageW, wt.BOOL, wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
_sig(user32.PostQuitMessage, None, ctypes.c_int)
_sig(user32.DefWindowProcW, LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_sig(user32.RegisterClassExW, wt.ATOM, ctypes.POINTER(WNDCLASSEXW))
_sig(user32.CreateWindowExW, wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID)
_sig(user32.DestroyWindow, wt.BOOL, wt.HWND)
_sig(user32.ShowWindow, wt.BOOL, wt.HWND, ctypes.c_int)
_sig(user32.MoveWindow, wt.BOOL, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.BOOL)
_sig(user32.GetClientRect, wt.BOOL, wt.HWND, ctypes.POINTER(wt.RECT))
_sig(user32.GetWindowRect, wt.BOOL, wt.HWND, ctypes.POINTER(wt.RECT))
_sig(user32.SetFocus, wt.HWND, wt.HWND)
_sig(user32.GetForegroundWindow, wt.HWND)
_sig(user32.SetForegroundWindow, wt.BOOL, wt.HWND)
_sig(user32.BringWindowToTop, wt.BOOL, wt.HWND)
_sig(user32.IsWindow, wt.BOOL, wt.HWND)
_sig(user32.IsWindowVisible, wt.BOOL, wt.HWND)
_sig(user32.GetAncestor, wt.HWND, wt.HWND, wt.UINT)
_sig(user32.WindowFromPoint, wt.HWND, wt.POINT)
_sig(user32.GetWindowThreadProcessId, wt.DWORD, wt.HWND, ctypes.POINTER(wt.DWORD))
_sig(user32.AttachThreadInput, wt.BOOL, wt.DWORD, wt.DWORD, wt.BOOL)
_sig(user32.GetWindowTextW, ctypes.c_int, wt.HWND, wt.LPWSTR, ctypes.c_int)
_sig(user32.GetWindowTextLengthW, ctypes.c_int, wt.HWND)
_sig(user32.FindWindowW, wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
_sig(user32.GetCursorPos, wt.BOOL, ctypes.POINTER(wt.POINT))
_sig(user32.SetCursorPos, wt.BOOL, ctypes.c_int, ctypes.c_int)
_sig(user32.SendInput, wt.UINT, wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_sig(user32.GetSystemMetrics, ctypes.c_int, ctypes.c_int)
_sig(user32.SystemParametersInfoW, wt.BOOL, wt.UINT, wt.UINT, wt.LPVOID, wt.UINT)
_sig(user32.LoadCursorW, wt.HANDLE, wt.HINSTANCE, wt.LPVOID)
_sig(user32.GetSysColorBrush, wt.HBRUSH, ctypes.c_int)
_sig(user32.UpdateWindow, wt.BOOL, wt.HWND)
_sig(user32.ClientToScreen, wt.BOOL, wt.HWND, ctypes.POINTER(wt.POINT))
_sig(kernel32.GetModuleHandleW, wt.HMODULE, wt.LPCWSTR)
_sig(kernel32.GetCurrentThreadId, wt.DWORD)
_sig(kernel32.OpenProcess, wt.HANDLE, wt.DWORD, wt.BOOL, wt.DWORD)
_sig(kernel32.CloseHandle, wt.BOOL, wt.HANDLE)
_sig(kernel32.QueryFullProcessImageNameW, wt.BOOL, wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD))
gdi32 = ctypes.WinDLL("gdi32")
_sig(gdi32.GetStockObject, wt.HANDLE, ctypes.c_int)


def dpi_aware():
    """Píxeles físicos por monitor (DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2); ignora si ya está fijado."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass


def cursor():
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def rect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def inside(pt, r):
    return r[0] <= pt[0] < r[2] and r[1] <= pt[1] < r[3]


def root_at(pt):
    h = user32.WindowFromPoint(wt.POINT(*pt))
    return user32.GetAncestor(h, GA_ROOT) if h else None


def title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, b, n + 1)
    return b.value


def window_pid(hwnd):
    pid = wt.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value, tid


def process_name(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        size = wt.DWORD(1024)
        b = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(size)):
            return b.value.replace("/", "\\").rsplit("\\", 1)[-1]
        return None
    finally:
        kernel32.CloseHandle(h)


def bring_front(hwnd, show=True):
    """Pone una ventana al frente (las del medidor; al final, la que el dueño tenía delante). SetForegroundWindow solo falla si el proceso no tiene el permiso de
    primer plano; entonces se une un instante a la cola de entrada del hilo delantero (AttachThreadInput), el
    recurso habitual que no inyecta ninguna tecla. Devuelve si quedó delante."""
    if user32.GetForegroundWindow() == hwnd:
        return True
    if show:
        user32.ShowWindow(hwnd, SW_SHOW)
    if user32.SetForegroundWindow(hwnd) and user32.GetForegroundWindow() == hwnd:
        return True
    me = kernel32.GetCurrentThreadId()
    fg = user32.GetForegroundWindow()
    _, fg_tid = window_pid(fg) if fg else (0, 0)
    attached = bool(fg_tid and fg_tid != me and user32.AttachThreadInput(me, fg_tid, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, fg_tid, False)
    return user32.GetForegroundWindow() == hwnd


def virtual_screen():
    g = user32.GetSystemMetrics
    return (g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN), g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN))


def send_move(x, y, mark):
    vx, vy, vw, vh = virtual_screen()
    i = INPUT(type=INPUT_MOUSE)
    i.mi = MOUSEINPUT(round((x - vx) * 65535 / max(1, vw - 1)), round((y - vy) * 65535 / max(1, vh - 1)), 0,
                      MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, mark)
    return user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))


def send_char(ch, mark):
    arr = (INPUT * 2)()
    for k, flags in enumerate((KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)):
        arr[k].type = INPUT_KEYBOARD
        arr[k].ki = KEYBDINPUT(0, ord(ch), flags, 0, mark)
    return user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def send_vk(vk, mark):
    """Una tecla virtual (bajada y subida) con esa marca en dwExtraInfo."""
    arr = (INPUT * 2)()
    for k, flags in enumerate((0, KEYEVENTF_KEYUP)):
        arr[k].type = INPUT_KEYBOARD
        arr[k].ki = KEYBDINPUT(vk, 0, flags, 0, mark)
    return user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def work_area():
    r = wt.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
    return (r.left, r.top, r.right, r.bottom)
