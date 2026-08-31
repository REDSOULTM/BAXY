using System.IO;
using System.Runtime.InteropServices;

namespace Baxy.App;

/// <summary>
/// Registers a queryable Win32 window class and a Shell_NotifyIcon entry.
/// Tests inject <see cref="ITrayIconShell"/> so they can assert NIM_ADD
/// without depending on the notification area layout of this session.
/// </summary>
internal sealed class PresenceTrayIcon : IDisposable
{
    internal const uint CallbackMessage = 0x8000 + 32;
    internal const uint ShowMessage = 0x8000 + 33;
    internal const uint ToggleListenMessage = 0x8000 + 34;
    internal const uint ExitMessage = 0x8000 + 35;
    internal const uint CommandShow = 1;
    internal const uint CommandListen = 2;
    internal const uint CommandExit = 3;

    private readonly ITrayIconShell _shell;
    private readonly WndProc _wndProc;
    private nint _classAtom;
    private nint _hwnd;
    private nint _icon;
    private bool _iconOwned;
    private bool _added;
    private bool _disposed;
    private bool _listening;

    internal PresenceTrayIcon(
        Action showWindow,
        Action toggleListen,
        Action exit,
        ITrayIconShell? shell = null)
    {
        ShowWindow = showWindow ?? throw new ArgumentNullException(nameof(showWindow));
        ToggleListen = toggleListen ?? throw new ArgumentNullException(nameof(toggleListen));
        Exit = exit ?? throw new ArgumentNullException(nameof(exit));
        _shell = shell ?? new ShellNotifyIcon();
        _wndProc = OnWindowMessage;
    }

    internal Action ShowWindow { get; }

    internal Action ToggleListen { get; }

    internal Action Exit { get; }

    internal nint Handle => _hwnd;

    internal bool IsRegistered => _hwnd != 0 && _added;

    internal static bool TryFind(out nint hwnd)
    {
        hwnd = NativeMethods.FindWindow(PresenceLimits.WindowClassName, PresenceLimits.WindowTitle);
        if (hwnd == 0)
        {
            hwnd = NativeMethods.FindWindow(PresenceLimits.WindowClassName, null);
        }

        return hwnd != 0;
    }

    internal void Start()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (_hwnd != 0)
        {
            return;
        }

        nint instance = NativeMethods.GetModuleHandle(null);
        var windowClass = new WindowClassEx
        {
            CbSize = (uint)Marshal.SizeOf<WindowClassEx>(),
            LpfnWndProc = Marshal.GetFunctionPointerForDelegate(_wndProc),
            HInstance = instance,
            LpszClassName = PresenceLimits.WindowClassName,
            HCursor = NativeMethods.LoadCursor(nint.Zero, new nint(32512)),
        };
        _classAtom = NativeMethods.RegisterClassEx(ref windowClass);
        if (_classAtom == 0)
        {
            int error = Marshal.GetLastWin32Error();
            if (error != 1410)
            {
                throw new InvalidOperationException("BAXY could not register its tray window class.");
            }
        }

        _hwnd = NativeMethods.CreateWindowEx(
            0,
            PresenceLimits.WindowClassName,
            PresenceLimits.WindowTitle,
            0,
            0,
            0,
            0,
            0,
            NativeMethods.HwndMessage,
            nint.Zero,
            instance,
            nint.Zero);
        if (_hwnd == 0)
        {
            throw new InvalidOperationException("BAXY could not create its tray window.");
        }

        _icon = ExtractOwnedIcon();
        _added = _shell.Add(_hwnd, CallbackMessage, _icon, "BAXY");
        if (!_added)
        {
            throw new InvalidOperationException("BAXY could not register in the notification area.");
        }
    }

    internal void SetListening(bool listening) => _listening = listening;

    internal bool Post(uint message) =>
        _hwnd != 0 && NativeMethods.PostMessage(_hwnd, message, nint.Zero, nint.Zero);

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        if (_hwnd != 0)
        {
            if (_added)
            {
                _ = _shell.Delete(_hwnd);
                _added = false;
            }

            _ = NativeMethods.DestroyWindow(_hwnd);
            _hwnd = 0;
        }

        if (_iconOwned && _icon != 0)
        {
            _ = NativeMethods.DestroyIcon(_icon);
            _icon = 0;
            _iconOwned = false;
        }
    }

    private nint OnWindowMessage(nint hwnd, uint message, nint wParam, nint lParam)
    {
        if (message == CallbackMessage)
        {
            int eventCode = unchecked((int)lParam.ToInt64() & 0xFFFF);
            if (eventCode is 0x0202 or 0x0400)
            {
                ShowWindow();
                return nint.Zero;
            }

            if (eventCode == 0x0205)
            {
                ShowContextMenu();
                return nint.Zero;
            }
        }

        if (message == ShowMessage)
        {
            ShowWindow();
            return nint.Zero;
        }

        if (message == ToggleListenMessage)
        {
            ToggleListen();
            return nint.Zero;
        }

        if (message == ExitMessage)
        {
            Exit();
            return nint.Zero;
        }

        if (message == 0x0111)
        {
            uint command = unchecked((uint)wParam.ToInt64() & 0xFFFF);
            if (command == CommandShow)
            {
                ShowWindow();
            }
            else if (command == CommandListen)
            {
                ToggleListen();
            }
            else if (command == CommandExit)
            {
                Exit();
            }

            return nint.Zero;
        }

        return NativeMethods.DefWindowProc(hwnd, message, wParam, lParam);
    }

    private void ShowContextMenu()
    {
        nint menu = NativeMethods.CreatePopupMenu();
        if (menu == 0)
        {
            return;
        }

        try
        {
            _ = NativeMethods.AppendMenu(menu, 0, new nint(CommandShow), "Mostrar BAXY");
            _ = NativeMethods.AppendMenu(
                menu,
                _listening ? 0x00000008u : 0,
                new nint(CommandListen),
                _listening ? "Dejar de escuchar" : "Escuchar");
            _ = NativeMethods.AppendMenu(menu, 0, new nint(CommandExit), "Salir");
            _ = NativeMethods.GetCursorPos(out Point point);
            _ = NativeMethods.SetForegroundWindow(_hwnd);
            _ = NativeMethods.TrackPopupMenu(
                menu,
                0x0100,
                point.X,
                point.Y,
                0,
                _hwnd,
                nint.Zero);
        }
        finally
        {
            _ = NativeMethods.DestroyMenu(menu);
        }
    }

    private nint ExtractOwnedIcon()
    {
        string exe = WindowsAutostartRegistration.ResolveCurrentExecutable();
        nint large = 0;
        nint small = 0;
        int extracted = NativeMethods.ExtractIconEx(exe, 0, out large, out small, 1);
        if (extracted > 0 && small != 0)
        {
            if (large != 0 && large != small)
            {
                _ = NativeMethods.DestroyIcon(large);
            }

            _iconOwned = true;
            return small;
        }

        if (large != 0)
        {
            _iconOwned = true;
            return large;
        }

        _iconOwned = false;
        return NativeMethods.LoadIcon(nint.Zero, new nint(32512));
    }

    private delegate nint WndProc(nint hwnd, uint message, nint wParam, nint lParam);

    private sealed class ShellNotifyIcon : ITrayIconShell
    {
        public bool Add(nint hwnd, uint callbackMessage, nint icon, string tip)
        {
            NotifyIconData data = CreateData(hwnd, callbackMessage, icon, tip);
            if (!NativeMethods.Shell_NotifyIcon(0, ref data))
            {
                return false;
            }

            data.UVersion = 4;
            _ = NativeMethods.Shell_NotifyIcon(4, ref data);
            return true;
        }

        public bool Delete(nint hwnd)
        {
            var data = new NotifyIconData
            {
                CbSize = (uint)Marshal.SizeOf<NotifyIconData>(),
                HWnd = hwnd,
                UId = 1,
            };
            return NativeMethods.Shell_NotifyIcon(2, ref data);
        }

        private static NotifyIconData CreateData(
            nint hwnd,
            uint callbackMessage,
            nint icon,
            string tip)
        {
            return new NotifyIconData
            {
                CbSize = (uint)Marshal.SizeOf<NotifyIconData>(),
                HWnd = hwnd,
                UId = 1,
                UFlags = 0x00000001 | 0x00000002 | 0x00000004 | 0x00000080,
                UCallbackMessage = callbackMessage,
                HIcon = icon,
                SzTip = tip,
            };
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NotifyIconData
    {
        public uint CbSize;
        public nint HWnd;
        public uint UId;
        public uint UFlags;
        public uint UCallbackMessage;
        public nint HIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string SzTip;
        public uint DwState;
        public uint DwStateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
        public string SzInfo;
        public uint UVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
        public string SzInfoTitle;
        public uint DwInfoFlags;
        public Guid GuidItem;
        public nint HBalloonIcon;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WindowClassEx
    {
        public uint CbSize;
        public uint Style;
        public nint LpfnWndProc;
        public int CbClsExtra;
        public int CbWndExtra;
        public nint HInstance;
        public nint HIcon;
        public nint HCursor;
        public nint HbrBackground;
        public string? LpszMenuName;
        public string LpszClassName;
        public nint HIconSm;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    private static class NativeMethods
    {
        internal static readonly nint HwndMessage = new(-3);

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern nint FindWindow(string lpClassName, string? lpWindowName);

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern nint RegisterClassEx(ref WindowClassEx windowClass);

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern nint CreateWindowEx(
            uint dwExStyle,
            string lpClassName,
            string lpWindowName,
            uint dwStyle,
            int x,
            int y,
            int nWidth,
            int nHeight,
            nint hWndParent,
            nint hMenu,
            nint hInstance,
            nint lpParam);

        [DllImport("user32.dll")]
        internal static extern nint DefWindowProc(nint hWnd, uint msg, nint wParam, nint lParam);

        [DllImport("user32.dll", SetLastError = true)]
        internal static extern bool DestroyWindow(nint hWnd);

        [DllImport("user32.dll", SetLastError = true)]
        internal static extern bool PostMessage(nint hWnd, uint msg, nint wParam, nint lParam);

        [DllImport("user32.dll")]
        internal static extern nint LoadCursor(nint hInstance, nint lpCursorName);

        [DllImport("user32.dll")]
        internal static extern nint LoadIcon(nint hInstance, nint lpIconName);

        [DllImport("user32.dll", SetLastError = true)]
        internal static extern bool DestroyIcon(nint hIcon);

        [DllImport("user32.dll")]
        internal static extern nint CreatePopupMenu();

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern bool AppendMenu(nint hMenu, uint uFlags, nint uIDNewItem, string lpNewItem);

        [DllImport("user32.dll")]
        internal static extern bool DestroyMenu(nint hMenu);

        [DllImport("user32.dll")]
        internal static extern bool GetCursorPos(out Point lpPoint);

        [DllImport("user32.dll")]
        internal static extern bool SetForegroundWindow(nint hWnd);

        [DllImport("user32.dll")]
        internal static extern bool TrackPopupMenu(
            nint hMenu,
            uint uFlags,
            int x,
            int y,
            int nReserved,
            nint hWnd,
            nint prcRect);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        internal static extern nint GetModuleHandle(string? lpModuleName);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        internal static extern int ExtractIconEx(
            string lpszFile,
            int nIconIndex,
            out nint phiconLarge,
            out nint phiconSmall,
            uint nIcons);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        internal static extern bool Shell_NotifyIcon(uint dwMessage, ref NotifyIconData lpData);
    }
}
