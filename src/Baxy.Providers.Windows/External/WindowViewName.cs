namespace Baxy.Providers.Windows.External;

/// <summary>
/// I13 (R5's review of I12, R5-1): the program a view names a window by, for a reader outside this assembly: a packaged
/// app's own for its ApplicationFrameHost frame (the shared host is never the process a look names), else the window's
/// own process; null when it cannot be read. The App reads the window in front with it, so that window bears the name
/// every receipt gives it (app_open's processName, a look's view, a typing's sentTo: OpenedWindowFront).
/// </summary>
public static class WindowViewName
{
    public static string? ProcessOf(nint window)
    {
        string name = VisibleControlSurface.ViewProcess(window).ProcessName;
        return name.Length > 0 ? name : null;
    }
}
