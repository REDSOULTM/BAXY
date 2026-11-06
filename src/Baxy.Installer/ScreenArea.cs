using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;

namespace Baxy.Installer;

/// <summary>The usable area of the monitor a window is on, in the window's own units (each monitor has its own scale).</summary>
internal static partial class ScreenArea
{
    private const uint NearestMonitor = 2;

    internal static Rect Of(Window window)
    {
        nint handle = new WindowInteropHelper(window).Handle;
        MonitorData monitor = new() { Size = (uint)Marshal.SizeOf<MonitorData>() };
        if (handle == 0 || !GetMonitorInfoW(MonitorFromWindow(handle, NearestMonitor), ref monitor))
        {
            return SystemParameters.WorkArea;
        }

        DpiScale dpi = VisualTreeHelper.GetDpi(window);
        return new Rect(
            monitor.WorkLeft / dpi.DpiScaleX,
            monitor.WorkTop / dpi.DpiScaleY,
            (monitor.WorkRight - monitor.WorkLeft) / dpi.DpiScaleX,
            (monitor.WorkBottom - monitor.WorkTop) / dpi.DpiScaleY);
    }

    [LibraryImport("user32.dll")]
    private static partial nint MonitorFromWindow(nint window, uint flags);

    [LibraryImport("user32.dll", EntryPoint = "GetMonitorInfoW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetMonitorInfoW(nint monitor, ref MonitorData data);

    [StructLayout(LayoutKind.Sequential)]
    private struct MonitorData
    {
        internal uint Size;
        internal int Left;
        internal int Top;
        internal int Right;
        internal int Bottom;
        internal int WorkLeft;
        internal int WorkTop;
        internal int WorkRight;
        internal int WorkBottom;
        internal uint Flags;
    }
}
