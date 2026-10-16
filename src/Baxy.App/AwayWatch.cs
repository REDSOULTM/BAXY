namespace Baxy.App;

/// <summary>
/// The person's absence as the heartbeat reads it (owner, 2026-10-16: while they are away a heartbeat only notifies;
/// when they come back it may greet them aloud). They are away from a look that reads them away
/// (<see cref="HeartbeatMoment.Away"/>: no input for <see cref="After"/>, no call, no window filling the screen), since
/// their last input; they are back at the first look with their input to the PC again (keyboard or mouse), never by the
/// microphone: a call that starts while they are away does not end it. Each change is the line the model reads.
/// </summary>
internal sealed class AwayWatch
{
    internal static readonly TimeSpan After = TimeSpan.FromMinutes(10);

    private DateTimeOffset? _since;

    /// <summary>
    /// One look at <paramref name="now"/>: <paramref name="idle"/> is the time since the person's last input, and
    /// <paramref name="away"/> whether the moment reads them away. The change it saw, or null.
    /// </summary>
    internal string? Look(DateTimeOffset now, TimeSpan idle, bool away)
    {
        if (_since is null)
        {
            if (!away)
            {
                return null;
            }

            _since = now - idle;
            return $"user idle: {(int)idle.TotalMinutes} min";
        }

        if (idle >= After)
        {
            return null;
        }

        // From their last input before leaving to their first one back.
        TimeSpan gone = now - idle - _since.Value;
        _since = null;
        return $"volvió tras {(int)gone.TotalMinutes} min ausente";
    }
}
