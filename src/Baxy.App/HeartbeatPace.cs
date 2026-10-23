namespace Baxy.App;

/// <summary>
/// When a look of the heartbeat may beat: the five-minute one at <see cref="Tick"/>, one with changes
/// <see cref="Spacing"/> after the last beat. Al máximo 10.5 (Need Help?, CHI 2025; Microsoft's notification guidance):
/// each change woke a beat of ~2.4 s in the mind's only slot, and the person's words waited behind it; what changes in
/// between waits in the heartbeat's list and goes in the next beat, so at most two run in a minute. None beats until
/// <see cref="AfterPerson"/> after the person's last turn (al máximo, flujos): they are talking with BAXY, and a beat
/// then took the slot their next words needed.
/// </summary>
internal sealed class HeartbeatPace(TimeProvider time)
{
    internal static readonly TimeSpan Tick = TimeSpan.FromMinutes(5);
    internal static readonly TimeSpan Spacing = TimeSpan.FromSeconds(30);
    internal static readonly TimeSpan AfterPerson = TimeSpan.FromSeconds(60);

    private DateTimeOffset _last = time.GetUtcNow();
    // When the person's last turn ended, in UTC ticks: written on the interface's thread, read on the heartbeat's.
    private long _person;

    /// <summary>Whether a look with <paramref name="changed"/> what it saw may beat now.</summary>
    internal bool Due(bool changed)
    {
        DateTimeOffset now = time.GetUtcNow();
        return now - _last >= (changed ? Spacing : Tick)
            && now.UtcTicks - Volatile.Read(ref _person) >= AfterPerson.Ticks;
    }

    /// <summary>A beat ran now, or the five-minute one was skipped (the person plays, the GPU is busy).</summary>
    internal void Beat() => _last = time.GetUtcNow();

    /// <summary>A turn of the person's ended now.</summary>
    internal void PersonTurn() => Volatile.Write(ref _person, time.GetUtcNow().UtcTicks);
}
