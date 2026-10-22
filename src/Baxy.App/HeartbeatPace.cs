namespace Baxy.App;

/// <summary>
/// When a look of the heartbeat may beat: the five-minute one at <see cref="Tick"/>, one with changes
/// <see cref="Spacing"/> after the last beat. Al máximo 10.5 (Need Help?, CHI 2025; Microsoft's notification guidance):
/// each change woke a beat of ~2.4 s in the mind's only slot, and the person's words waited behind it; what changes in
/// between waits in the heartbeat's list and goes in the next beat, so at most two run in a minute.
/// </summary>
internal sealed class HeartbeatPace(TimeProvider time)
{
    internal static readonly TimeSpan Tick = TimeSpan.FromMinutes(5);
    internal static readonly TimeSpan Spacing = TimeSpan.FromSeconds(30);

    private DateTimeOffset _last = time.GetUtcNow();

    /// <summary>Whether a look with <paramref name="changed"/> what it saw may beat now.</summary>
    internal bool Due(bool changed) => time.GetUtcNow() - _last >= (changed ? Spacing : Tick);

    /// <summary>A beat ran now, or the five-minute one was skipped (the person plays, the GPU is busy).</summary>
    internal void Beat() => _last = time.GetUtcNow();
}
