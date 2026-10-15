namespace Baxy.Providers.Windows.External;

/// <summary>
/// Ronda 21, destino por contenido (pasada r18: t-file-1, t-file-3, t-menu-4, t-form-4, t-drag-2): a mission that names
/// no application looked only at the window in front, the person's own, and the window that holds what the request
/// names (an unsaved document, a selection, a menu or a panel by its name) was never looked at. The windows a person
/// sees on the desktop, top of the Z order first, are the candidates the App weighs against the request's referent.
/// </summary>
internal static partial class VisibleControlSurface
{
    /// <summary>
    /// One root window of the desktop as the destination's search sees it: its process, title, the person's last input
    /// to it, and whether it is cloaked (on another virtual desktop, a suspended packaged app: not seen by the person).
    /// </summary>
    internal readonly record struct DestinationWindow(
        nint Window, int ProcessId, string Process, string Title, long? PersonInputAgoMs, bool Cloaked);

    /// <summary>
    /// The desktop's usable root windows in Z order (top first): visible, not a tool window, not BAXY's process, not the
    /// desktop or the taskbar. Cloaked ones come marked and the caller leaves them out; the developer's and BAXY's own
    /// processes come too and the caller marks them (<see cref="ProtectedFrom"/>): the App never takes them. The root
    /// window in front comes with them.
    /// </summary>
    internal static (IReadOnlyList<DestinationWindow> Windows, nint Front) DestinationDesktop()
    {
        RootSnapshot snapshot = RootWindowsNow(0);
        WindowsUserInputPause pause = WindowsUserInputPause.Shared;
        return ([.. snapshot.Windows.Select(window =>
            {
                (int processId, string process) = ViewProcess(window.Window);
                return new DestinationWindow(
                    window.Window, processId, process, WindowTitle(window.Window), pause.PersonInputAgoMs(window.Window),
                    DwmGetWindowAttribute(window.Window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0);
            })],
            snapshot.Front);
    }
}
