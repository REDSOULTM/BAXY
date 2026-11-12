namespace Baxy.App;

/// <summary>
/// OVL1: when a button that authorizes an effect takes a press. A press counts only if the person made it after the
/// button was drawn armed, and the button is drawn armed only once it has been in its place, drawn off, for the whole
/// wait. Every time is the caller's: when the button was drawn, and when the press was made (the time of its input
/// message), never when the window's thread got round to handling it. The overlay's first guard compared the time its
/// handler ran with the time the card arrived: with the thread busy for half a second (a burst of events on a new
/// card), a click 200 ms after the Sí was painted was handled late enough to approve, the lag Mozilla's CVE-2023-34414
/// names (MFSA 2023-20, «click-jacking … through rendering lag»). Chromium compares the event's own time stamp
/// (ui/views/input_event_activation_protector.cc).
/// </summary>
internal sealed class ApprovalGuard(int wait)
{
    private long? _placed;
    private long? _armed;

    /// <summary>Whether the button is to look armed (it takes presses only once drawn so: <see cref="Armed"/>).</summary>
    internal bool IsLit { get; private set; }

    /// <summary>
    /// The wait, given the system's double-click time: one second, as Firefox holds the buttons of its security dialogs
    /// (security.dialog_enable_delay = 1000 ms, modules/libpref/init/all.js), and never less than the system's
    /// double-click time, Chromium's measure of two presses meant as one (GetDoubleClickInterval).
    /// </summary>
    internal static int Wait(uint doubleClick) => (int)Math.Max(1000, Math.Min(doubleClick, int.MaxValue));

    /// <summary>
    /// The button is another one, moved, changed size, came back to view, or was pressed too soon: the wait starts
    /// again once it is drawn (Chromium's WindowsStationarityMonitor and Firefox's PopupNotifications, which also pushes
    /// its time forward on an early click).
    /// </summary>
    internal void Restart()
    {
        _placed = null;
        _armed = null;
        IsLit = false;
    }

    /// <summary>The button was drawn in its place, off.</summary>
    internal void Placed(long now) => _placed ??= now;

    /// <summary>Milliseconds until the button may be lit; null while it is not drawn in its place, or already lit.</summary>
    internal long? Left(long now) => IsLit || _placed is not { } placed ? null : Math.Max(0, placed + wait - now);

    /// <summary>Lights the button if its wait is over; says whether it is lit.</summary>
    internal bool Light(long now)
    {
        if (Left(now) == 0)
        {
            IsLit = true;
        }

        return IsLit;
    }

    /// <summary>The lit button was drawn.</summary>
    internal void Armed(long now)
    {
        if (IsLit)
        {
            _armed ??= now;
        }
    }

    /// <summary>Whether a press made at that time counts.</summary>
    internal bool Takes(long pressedAt) => _armed is { } armed && pressedAt >= armed;
}
