using System.Diagnostics;

namespace Baxy.Providers.Windows.SystemStatus;

public sealed class WindowsProcessStatusProvider : IProcessStatusProvider
{
    private const int MaximumObservedProcesses = 4_096;

    public async ValueTask<ProcessStatusSnapshot> GetProcessesAsync(
        ProcessStatusSort sort,
        int limit,
        CancellationToken cancellationToken)
    {
        if (limit is < 1 or > 50)
        {
            throw new ArgumentOutOfRangeException(nameof(limit));
        }

        if (!Enum.IsDefined(sort))
        {
            throw new ArgumentOutOfRangeException(nameof(sort));
        }
        cancellationToken.ThrowIfCancellationRequested();
        int? logicalProcessorCount = sort == ProcessStatusSort.Cpu
            ? new WindowsSystemStatusProbe().ReadLogicalProcessorCount()
            : null;
        Dictionary<ProcessIdentity, ProcessSample> first = Observe(
            cancellationToken);
        if (sort == ProcessStatusSort.Cpu)
        {
            await Task.Delay(WindowsSystemStatusProvider.DefaultCpuSamplingInterval,
                cancellationToken).ConfigureAwait(false);
        }
        Dictionary<ProcessIdentity, ProcessSample> second = Observe(
            cancellationToken);
        return CreateSnapshot(first, second, sort, limit, logicalProcessorCount);
    }

    internal static ProcessStatusSnapshot CreateSnapshot(
        IReadOnlyDictionary<ProcessIdentity, ProcessSample> first,
        IReadOnlyDictionary<ProcessIdentity, ProcessSample> second,
        ProcessStatusSort sort,
        int limit,
        int? logicalProcessorCount)
    {
        IEnumerable<ProcessStatusEntry> stable = second
            .Where(pair => first.ContainsKey(pair.Key))
            .Select(pair => sort == ProcessStatusSort.Cpu
                ? MeasureCpu(first[pair.Key], pair.Value, logicalProcessorCount)
                : pair.Value.Entry)
            .OfType<ProcessStatusEntry>();
        stable = sort switch
        {
            ProcessStatusSort.Cpu => stable
                .OrderByDescending(static item => item.CpuUsagePercent)
                .ThenBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static item => item.ProcessId),
            ProcessStatusSort.Memory => stable
                .OrderByDescending(static item => item.WorkingSetBytes)
                .ThenBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static item => item.ProcessId),
            ProcessStatusSort.Name => stable
                .OrderBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static item => item.ProcessId),
            _ => throw new ArgumentOutOfRangeException(nameof(sort)),
        };
        return new ProcessStatusSnapshot(
            second.Count,
            stable.Take(limit).ToArray(),
            logicalProcessorCount);
    }

    private static ProcessStatusEntry? MeasureCpu(
        ProcessSample first,
        ProcessSample second,
        int? logicalProcessorCount)
    {
        double elapsed = Stopwatch.GetElapsedTime(first.Timestamp, second.Timestamp).TotalSeconds;
        double processorSeconds = second.Entry.TotalProcessorSeconds - first.Entry.TotalProcessorSeconds;
        if (logicalProcessorCount is null or < 1 || elapsed <= 0
            || !double.IsFinite(processorSeconds) || processorSeconds < 0)
        {
            return null;
        }
        // Normalize to the whole machine, not this process's affinity or CPU quota.
        // Counter granularity can slightly exceed physical capacity over a short sample.
        return second.Entry with
        {
            CpuUsagePercent = Math.Clamp(processorSeconds / elapsed / logicalProcessorCount.Value * 100, 0, 100),
            SampleDurationSeconds = elapsed,
        };
    }

    private static Dictionary<ProcessIdentity, ProcessSample> Observe(
        CancellationToken cancellationToken)
    {
        Process[] processes = Process.GetProcesses();
        try
        {
            var result = new Dictionary<ProcessIdentity, ProcessSample>();
            foreach (Process process in processes.Take(MaximumObservedProcesses))
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    process.Refresh();
                    string name = process.ProcessName;
                    long created = process.StartTime.ToUniversalTime().Ticks;
                    var identity = new ProcessIdentity(process.Id, created, name);
                    var entry = new ProcessStatusEntry(
                        process.Id,
                        created,
                        name,
                        Math.Max(0, process.WorkingSet64),
                        Math.Max(0, process.TotalProcessorTime.TotalSeconds));
                    result[identity] = new ProcessSample(entry, Stopwatch.GetTimestamp());
                }
                catch (Exception error) when (error is
                    InvalidOperationException or NotSupportedException or
                    System.ComponentModel.Win32Exception)
                {
                    // A process can exit or deny observation between enumeration
                    // and measurement. It is omitted instead of guessed.
                }
                catch (OutOfMemoryException)
                {
                    // Windows can temporarily refuse another process snapshot
                    // while the local model is consuming most committed memory.
                    // Preserve the already observed, verified subset instead of
                    // failing the whole status request or repeatedly allocating.
                    break;
                }
            }
            return result;
        }
        finally
        {
            foreach (Process process in processes)
            {
                process.Dispose();
            }
        }
    }

    internal sealed record ProcessSample(ProcessStatusEntry Entry, long Timestamp);

    internal sealed record ProcessIdentity(
        int ProcessId,
        long CreationTimeUtcTicks,
        string Name);
}
