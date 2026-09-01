namespace Baxy.App;

/// <summary>
/// Attributed idle samples for the BAXY process tree. Unit tests inject the
/// reader and never wait 15 minutes.
/// </summary>
internal sealed class PresenceIdleSampler
{
    internal const long DefaultWorkingSetGrowthBytes = 8L * 1024 * 1024;
    internal const long DefaultHandleGrowth = 100;
    internal const double DefaultProcessTreeCpuPercent = 5;

    private readonly IPresenceProcessReader _reader;
    private readonly IPresenceClock _clock;
    private readonly List<PresenceIdleSnapshot> _samples = [];

    internal PresenceIdleSampler(
        IPresenceProcessReader reader,
        IPresenceClock? clock = null)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
        _clock = clock ?? new SystemPresenceClock();
    }

    internal IReadOnlyList<PresenceIdleSnapshot> Samples => _samples;

    internal PresenceIdleSnapshot Capture(
        bool ready,
        bool inputEnabled,
        bool listening,
        DateTimeOffset? firstWakeUtc,
        string terminal)
    {
        var snapshot = new PresenceIdleSnapshot(
            _clock.UtcNow,
            ready,
            inputEnabled,
            listening,
            firstWakeUtc,
            terminal,
            _reader.ReadOwned());
        _samples.Add(snapshot);
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

    internal static bool ExceedsVramCeiling(PresenceIdleSnapshot snapshot) =>
        TotalVram(snapshot) > PresenceLimits.VramCeilingBytes;

    internal static bool HasUnattributedProcess(PresenceIdleSnapshot snapshot) =>
        snapshot.Processes.Any(static process =>
            process.ProcessId <= 0
            || string.IsNullOrWhiteSpace(process.Name)
            || string.IsNullOrWhiteSpace(process.Path));

    internal bool HasMonotonicWorkingSetGrowth(long thresholdBytes = DefaultWorkingSetGrowthBytes)
    {
        if (_samples.Count < 3)
        {
            return false;
        }

        long first = TotalWorkingSet(_samples[0]);
        long last = TotalWorkingSet(_samples[^1]);
        if (last - first < thresholdBytes)
        {
            return false;
        }

        for (int index = 1; index < _samples.Count; index++)
        {
            if (TotalWorkingSet(_samples[index]) < TotalWorkingSet(_samples[index - 1]))
            {
                return false;
            }
        }

        return true;
    }

    internal bool HasMonotonicHandleGrowth(long threshold = DefaultHandleGrowth)
    {
        if (_samples.Count < 3)
        {
            return false;
        }

        long first = TotalHandles(_samples[0]);
        long last = TotalHandles(_samples[^1]);
        if (last - first < threshold)
        {
            return false;
        }

        for (int index = 1; index < _samples.Count; index++)
        {
            if (TotalHandles(_samples[index]) < TotalHandles(_samples[index - 1]))
            {
                return false;
            }
        }

        return true;
    }

    internal bool HasAvoidableProcessTreeSpin(
        double thresholdPercent = DefaultProcessTreeCpuPercent,
        int logicalProcessorCount = 0)
    {
        if (_samples.Count < 2)
        {
            return false;
        }

        int processors = logicalProcessorCount > 0
            ? logicalProcessorCount
            : Environment.ProcessorCount;
        double peakPercent = 0;
        for (int index = 1; index < _samples.Count; index++)
        {
            PresenceIdleSnapshot before = _samples[index - 1];
            PresenceIdleSnapshot after = _samples[index];
            double wallSeconds = (after.Utc - before.Utc).TotalSeconds;
            if (wallSeconds <= 0)
            {
                continue;
            }

            Dictionary<(int ProcessId, string Path), double> beforeCpu =
                before.Processes.ToDictionary(
                    static process => (process.ProcessId, process.Path),
                    static process => process.CpuSeconds);
            double cpuDelta = after.Processes.Sum(process =>
                beforeCpu.TryGetValue(
                    (process.ProcessId, process.Path),
                    out double previous)
                    ? Math.Max(0, process.CpuSeconds - previous)
                    : 0);
            peakPercent = Math.Max(
                peakPercent,
                cpuDelta / wallSeconds / processors * 100.0);
        }

        return peakPercent > thresholdPercent;
    }

    internal static IReadOnlyDictionary<string, long> WorkingSetByProcess(
        PresenceIdleSnapshot snapshot)
    {
        var totals = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
        foreach (PresenceProcessSample process in snapshot.Processes)
        {
            totals[process.Name] = totals.GetValueOrDefault(process.Name) + process.WorkingSetBytes;
        }

        return totals;
    }

}
