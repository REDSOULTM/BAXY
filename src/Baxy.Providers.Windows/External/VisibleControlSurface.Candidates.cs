namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría final V3: a look that names an application no window is goes back with the windows a person sees on the
/// desktop, top of the Z order first, for the model to name one exactly
/// (<see cref="WindowsVisibleControlAdapter.NamedWindowNotFound"/>).
/// </summary>
internal static partial class VisibleControlSurface
{
    /// <summary>
    /// One root window of the desktop as a candidate: its process, its title, and whether it is cloaked (on another
    /// virtual desktop, a suspended packaged app: not seen by the person).
    /// </summary>
    internal readonly record struct DestinationWindow(string Process, string Title, bool Cloaked);

    /// <summary>
    /// The desktop's usable root windows in Z order (top first): visible, not a tool window, not BAXY's process, not the
    /// desktop or the taskbar. Cloaked ones come marked and the caller leaves them out.
    /// </summary>
    internal static IReadOnlyList<DestinationWindow> DestinationDesktop() =>
        [.. RootWindowsNow(0).Windows.Select(window => new DestinationWindow(
            ViewProcess(window.Window).ProcessName, WindowTitle(window.Window),
            DwmGetWindowAttribute(window.Window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0))];
}
