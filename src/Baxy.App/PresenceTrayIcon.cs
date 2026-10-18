using System.IO;
using System.Runtime.InteropServices;

namespace Baxy.App;

/// <summary>
/// Registers a Win32 window class for its own messages and a Shell_NotifyIcon entry. A click (or Enter) on the icon
/// opens BAXY; the right button (or the menu key) asks for BAXY's own menu at the pointer
/// (<see cref="Presentation.TrayMenu"/>), drawn by the presence instead of a native popup menu.
/// </summary>
internal sealed class PresenceTrayIcon : IDisposable
{
    internal const uint CallbackMessage = 0x8000 + 32;

    private readonly WndProc _wndProc;
    // FT/proveedores goal (review of the App): Explorer, started again, broadcasts this; every notification icon is gone
    // and is added again on it (Microsoft, «Taskbar Creation Notification»).
    private static readonly uint TaskbarCreated = NativeMethods.RegisterWindowMessage("TaskbarCreated");
    private nint _classAtom;
    private nint _hwnd;
    private nint _icon;
    private bool _iconOwned;
    private bool _added;
    private bool _disposed;

    internal PresenceTrayIcon(Action showWindow, Action<int, int> showMenu)
    {
        ShowWindow = showWindow ?? throw new ArgumentNullException(nameof(showWindow));
        ShowMenu = showMenu ?? throw new ArgumentNullException(nameof(showMenu));
        _wndProc = OnWindowMessage;
    }

    internal Action ShowWindow { get; }

    /// <summary>BAXY's menu at this point of the screen (device pixels).</summary>
    internal Action<int, int> ShowMenu { get; }

    internal bool IsRegistered => _hwnd != 0 && _added;

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

        // A hidden top-level tool window, not a message-only one: a message-only window receives no broadcast, so
        // TaskbarCreated never came and after Explorer restarted BAXY had no icon for good. Never shown, it is in no
        // task bar nor Alt+Tab (WS_EX_TOOLWINDOW).
        _hwnd = NativeMethods.CreateWindowEx(
            0x00000080,
            PresenceLimits.WindowClassName,
            PresenceLimits.WindowTitle,
            0,
            0,
            0,
            0,
            0,
            nint.Zero,
            nint.Zero,
            instance,
            nint.Zero);
        if (_hwnd == 0)
        {
            throw new InvalidOperationException("BAXY could not create its tray window.");
        }

        _icon = ExtractOwnedIcon();
        _added = ShellNotifyIcon.Add(_hwnd, CallbackMessage, _icon, "BAXY");
        if (!_added)
        {
            throw new InvalidOperationException("BAXY could not register in the notification area.");
        }
    }

    internal bool Notify(string text) => IsRegistered && ShellNotifyIcon.Notify(_hwnd, text);

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
                _ = ShellNotifyIcon.Delete(_hwnd);
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
        if (TaskbarCreated != 0 && message == TaskbarCreated && !_disposed && _hwnd != 0)
        {
            _added = ShellNotifyIcon.Add(_hwnd, CallbackMessage, _icon, "BAXY");
            return nint.Zero;
        }

        if (message == CallbackMessage)
        {
            // NOTIFYICON_VERSION_4: the event is lParam's low word. A click or NIN_SELECT/NIN_KEYSELECT opens BAXY;
            // the right button or WM_CONTEXTMENU (the menu key) asks for the menu. (The native menu this replaced was
            // opened with TPM_RETURNCMD and its choice was dropped: no row ever ran.)
            int eventCode = unchecked((int)lParam.ToInt64() & 0xFFFF);
            if (eventCode is 0x0202 or 0x0400 or 0x0401)
            {
                ShowWindow();
                return nint.Zero;
            }

            if (eventCode is 0x0205 or 0x007B)
            {
                _ = NativeMethods.GetCursorPos(out Point point);
                ShowMenu(point.X, point.Y);
                return nint.Zero;
            }
        }

        return NativeMethods.DefWindowProc(hwnd, message, wParam, lParam);
    }

    // BAXY's icon (the executable's, ApplicationIcon) at the size the notification area draws at this DPI.
    private nint ExtractOwnedIcon()
    {
        string exe = WindowsAutostartRegistration.ResolveCurrentExecutable();
        int size = NativeMethods.GetSystemMetricsForDpi(49, NativeMethods.GetDpiForSystem()); // SM_CXSMICON
        if (size <= 0)
        {
            size = 16;
        }

        if (NativeMethods.SHDefExtractIcon(exe, 0, 0, out nint large, out nint small, (uint)(size << 16 | size)) == 0
            && small != 0)
        {
            if (large != 0)
            {
                _ = NativeMethods.DestroyIcon(large);
            }

            _iconOwned = true;
            return small;
        }

        _iconOwned = false;
        return NativeMethods.LoadIcon(nint.Zero, new nint(32512));
    }

    private delegate nint WndProc(nint hwnd, uint message, nint wParam, nint lParam);

    private static class ShellNotifyIcon
    {
        public static bool Add(nint hwnd, uint callbackMessage, nint icon, string tip)
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

        // A notification on screen from the tray icon (the heartbeat's words when they are not spoken).
        public static bool Notify(nint hwnd, string text)
        {
            var data = new NotifyIconData
            {
                CbSize = (uint)Marshal.SizeOf<NotifyIconData>(),
                HWnd = hwnd,
                UId = 1,
                UFlags = 0x00000010,
                SzInfo = text.Length > 255 ? text[..254] + "…" : text,
                SzInfoTitle = "BAXY",
                DwInfoFlags = 0x00000001,
                SzTip = string.Empty,
            };
            return NativeMethods.Shell_NotifyIcon(1, ref data);
        }

        public static bool Delete(nint hwnd)
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

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern uint RegisterWindowMessage(string lpString);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern nint DefWindowProc(nint hWnd, uint msg, nint wParam, nint lParam);

        [DllImport("user32.dll", SetLastError = true)]
        internal static extern bool DestroyWindow(nint hWnd);

        [DllImport("user32.dll")]
        internal static extern nint LoadCursor(nint hInstance, nint lpCursorName);

        [DllImport("user32.dll")]
        internal static extern nint LoadIcon(nint hInstance, nint lpIconName);

        [DllImport("user32.dll", SetLastError = true)]
        internal static extern bool DestroyIcon(nint hIcon);

        [DllImport("user32.dll")]
        internal static extern bool GetCursorPos(out Point lpPoint);

        [DllImport("user32.dll")]
        internal static extern uint GetDpiForSystem();

        [DllImport("user32.dll")]
        internal static extern int GetSystemMetricsForDpi(int nIndex, uint dpi);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        internal static extern nint GetModuleHandle(string? lpModuleName);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        internal static extern int SHDefExtractIcon(
            string pszIconFile,
            int iIndex,
            uint uFlags,
            out nint phiconLarge,
            out nint phiconSmall,
            uint nIconSize);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        internal static extern bool Shell_NotifyIcon(uint dwMessage, ref NotifyIconData lpData);
    }
}
