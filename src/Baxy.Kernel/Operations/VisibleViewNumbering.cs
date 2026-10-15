namespace Baxy.Kernel.Operations;

/// <summary>
/// Ronda 23 (índices de vista y esquema; t-menu-2 r21): one range of control indexes end to end. The worker
/// (DesktopUiaWorker.ps1, Do-View) numbers a look from 0: at most <see cref="Cap"/> controls of the window, then up to
/// <see cref="WantedRoom"/> controls kept for the goal's words («reserved»), then the window's content surface
/// (<see cref="Body"/>). The catalog's acts on a control of the look (click, scroll, type, drag) accept every index the
/// look can number; a test reads the worker's own constants and runs its join over a full view against this range.
/// </summary>
public static class VisibleViewNumbering
{
    /// <summary>The cap of a look (the worker's <c>$script:ViewCap</c>, the App's <c>limit</c>).</summary>
    public const int Cap = 60;

    /// <summary>The controls kept past the cap for the goal's words (the worker's <c>$script:WantedRoom</c>).</summary>
    public const int WantedRoom = 10;

    /// <summary>The window's content surface, always listed past everything else.</summary>
    public const int Body = 1;

    /// <summary>The highest index a look can number.</summary>
    public const int HighestIndex = Cap + WantedRoom + Body - 1;
}
