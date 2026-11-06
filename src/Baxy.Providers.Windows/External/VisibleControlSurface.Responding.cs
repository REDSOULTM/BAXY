using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    /// <summary>The code of an act refused, with nothing sent, because its window's thread does not pump messages.</summary>
    internal const string WindowNotResponding = "window_not_responding";

    /// <summary>The reason a look at such a window gives the model («uiaFailed»).</summary>
    internal const string NotRespondingReason = "la ventana no responde";

    private const uint NullMessage = 0;
    private const uint AbortIfHung = 2;
    private const uint ProbeTimeoutMs = 500;
    private const int GiveUpMs = 6_000;
    private const int ErrorTimeout = 1460;
    private const string GhostClass = "Ghost";

    /// <summary>
    /// uso-108 A9 (measured live on a window of a test whose thread stopped pumping): FromHandle on the managed client and
    /// BringWindowToTop, SetWindowPos, MoveWindow and ShowWindow block inside the call for as long as the window does (past
    /// 40 s; agent-desktop <c>automation.rs:215-252</c>, FINDINGS A14-11), and a key sent to it waits in its queue and arrives
    /// when it comes back. So before a window is touched: gone is not hung (<c>IsWindow</c> first, <c>automation.rs:261-264</c>);
    /// then WM_NULL with SMTO_ABORTIFHUNG (<c>window_enum.rs:216-237</c>), about 0 ms on a window that pumps. A busy window is
    /// not a frozen one, and a document opening or a sheet recalculating is busy for seconds: review of uso-108, two probes of
    /// 500 ms refused one busy for 1 s. So the probe keeps asking until the window answers (the act then goes on, late) or until
    /// Windows itself calls it hung (IsHungAppWindow, about 5 s without pumping, measured 5.0 s; agent-desktop
    /// <c>process_state_tests.rs:274</c>), bounded at 6 s. The wait is paid once: on a window already marked it is asked first,
    /// 0 ms (SMTO_ABORTIFHUNG alone still took its 500 ms on one that never showed, measured). After 5 s
    /// Windows may show a window of
    /// class Ghost in its place, of the desktop manager, with its title (measured: the front and the search by name find
    /// that one; it answers, and takes nothing): it stands for a window that does not respond. A window that may not be
    /// messaged (UIPI, ERROR_ACCESS_DENIED) says nothing about its thread. A window that answers here may still stop right
    /// after: the writes on a target window are the async forms too, and the worker's budget stays
    /// (<c>fixture_hung_after_probe.rs</c>).
    /// </summary>
    internal static bool NotResponding(nint window) => NotResponding(window, CancellationToken.None);

    /// <summary>The check above; the wait for a busy window ends with the request, within one probe.</summary>
    internal static bool NotResponding(nint window, CancellationToken cancellationToken)
    {
        if (window == 0 || !IsWindow(window))
            return false;
        if (IsGhost(window))
            return true;
        long began = Environment.TickCount64;
        while (!IsHungAppWindow(window))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (Answers(window))
                return false;
            if (Environment.TickCount64 - began >= GiveUpMs)
                return true;
            Thread.Sleep(10);
        }

        return true;
    }

    internal static bool IsGhost(nint window) => string.Equals(ClassName(window), GhostClass, StringComparison.Ordinal);

    private static bool Answers(nint window)
    {
        if (SendMessageTimeoutW(window, NullMessage, 0, 0, AbortIfHung, ProbeTimeoutMs, out _) != 0)
            return true;
        int error = Marshal.GetLastPInvokeError();
        return error != 0 && error != ErrorTimeout;
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsHungAppWindow(nint window);

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial nint SendMessageTimeoutW(
        nint window, uint message, nint wParam, nint lParam, uint flags, uint timeoutMs, out nint result);
}
