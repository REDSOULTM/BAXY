namespace Baxy.App;

/// <summary>
/// Attributed idle samples for the BAXY process tree. Unit tests inject the
/// reader and never wait 15 minutes. Only the latest samples stay in memory
/// (one hour at the 15 s period), so the App's own memory does not grow with the
/// time it stays open.
/// </summary>
internal sealed class PresenceIdleSampler
{
    internal const int DefaultRetainedSamples = 240;

    private readonly IPresenceProcessReader _reader;
    private readonly IPresenceClock _clock;
    private readonly int _retainedSamples;
    private readonly List<PresenceIdleSnapshot> _samples = [];

    internal PresenceIdleSampler(
        IPresenceProcessReader reader,
        IPresenceClock? clock = null,
        int retainedSamples = DefaultRetainedSamples)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
        _clock = clock ?? new SystemPresenceClock();
        ArgumentOutOfRangeException.ThrowIfLessThan(retainedSamples, 1);
        _retainedSamples = retainedSamples;
    }

    internal IReadOnlyList<PresenceIdleSnapshot> Samples => _samples;

    /// <summary>
    /// The process read (toolhelp walk, handle counts and the GPU tool) runs on
    /// the thread pool; the caller's context only records the finished sample,
    /// so a slow read never holds the window's thread.
    /// </summary>
    internal async Task<PresenceIdleSnapshot> CaptureAsync(
        bool ready,
        bool inputEnabled,
        bool listening,
        DateTimeOffset? firstWakeUtc,
        string terminal)
    {
        IReadOnlyList<PresenceProcessSample> processes = await Task.Run(_reader.ReadOwned);
        return Record(ready, inputEnabled, listening, firstWakeUtc, terminal, processes);
    }

    private PresenceIdleSnapshot Record(
        bool ready,
        bool inputEnabled,
        bool listening,
        DateTimeOffset? firstWakeUtc,
        string terminal,
        IReadOnlyList<PresenceProcessSample> processes)
    {
        var snapshot = new PresenceIdleSnapshot(
            _clock.UtcNow,
            ready,
            inputEnabled,
            listening,
            firstWakeUtc,
            terminal,
            processes);
        _samples.Add(snapshot);
        if (_samples.Count > _retainedSamples)
        {
            _samples.RemoveRange(0, _samples.Count - _retainedSamples);
        }

        return snapshot;
    }

    internal static long TotalWorkingSet(PresenceIdleSnapshot snapshot) =>
        snapshot.Processes.Sum(static process => process.WorkingSetBytes);

    internal static long TotalHandles(PresenceIdleSnapshot snapshot) =>
        snapshot.Processes.Sum(static process => process.HandleCount);

    internal static long TotalVram(PresenceIdleSnapshot snapshot) =>
        snapshot.Processes.Sum(static process => process.VramBytes);

    internal static double TotalCpuSeconds(PresenceIdleSnapshot snapshot) =>
        snapshot.Processes.Sum(static process => process.CpuSeconds);
}
