using System.Collections.Concurrent;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// An off-screen window of a test that takes no activation, on a thread of its own that pumps messages. On the test's own
/// thread, blocked on a result, it does not answer: the adapter's check calls it not responding (uso-108 A9), rightly.
/// </summary>
internal static class PumpedWindow
{
    private const uint Quit = 0x0012;

    private static readonly ConcurrentDictionary<nint, (Thread Thread, uint Id)> Pumps = new();

    internal static nint Create(string title)
    {
        nint window = 0;
        uint threadId = 0;
        using var ready = new ManualResetEventSlim();
        var thread = new Thread(() =>
        {
            threadId = GetCurrentThreadId();
            window = CreateWindowExW(0x08000080, "STATIC", title, 0x90000000u, -31000, -31000, 200, 120, 0, 0, 0, 0);
            ready.Set();
            while (GetMessageW(out Message message, 0, 0, 0) > 0)
                _ = DispatchMessageW(ref message);
            _ = DestroyWindow(window);
        })
        {
            IsBackground = true,
            Name = "PumpedWindow",
        };
        thread.Start();
        ready.Wait();
        Pumps[window] = (thread, threadId);
        return window;
    }

    internal static void Destroy(nint window)
    {
        if (!Pumps.TryRemove(window, out (Thread Thread, uint Id) pump))
            return;
        _ = PostThreadMessageW(pump.Id, Quit, 0, 0);
        pump.Thread.Join(TimeSpan.FromSeconds(5));
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Message
    {
        public nint Window;
        public uint Id;
        public nint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
    }

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint CreateWindowExW(uint extendedStyle, string className, string title, uint style,
        int x, int y, int width, int height, nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetMessageW(out Message message, nint window, uint minimum, uint maximum);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint DispatchMessageW(ref Message message);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostThreadMessageW(uint thread, uint message, nint wParam, nint lParam);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);
}
