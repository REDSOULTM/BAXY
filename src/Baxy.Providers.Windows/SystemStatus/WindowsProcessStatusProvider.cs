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
            cancellationToken, out bool firstComplete, out _);
        if (sort == ProcessStatusSort.Cpu)
        {
            await Task.Delay(WindowsSystemStatusProvider.DefaultCpuSamplingInterval,
                cancellationToken).ConfigureAwait(false);
        }
        Dictionary<ProcessIdentity, ProcessSample> second = Observe(
            cancellationToken, out bool secondComplete, out int denied);
        return CreateSnapshot(first, second, sort, limit, logicalProcessorCount)
            with { ObservationComplete = firstComplete && secondComplete, UnmeasuredProcessCount = denied };
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
        CancellationToken cancellationToken,
        out bool complete,
        out int denied)
    {
        denied = 0;
        Process[] processes = Process.GetProcesses();
        complete = processes.Length <= MaximumObservedProcesses;
        try
        {
            var result = new Dictionary<ProcessIdentity, ProcessSample>();
            foreach (Process process in processes.Take(MaximumObservedProcesses))
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    // Renew al máximo (w8): Process.GetProcesses already holds each process's fresh data; Refresh()
                    // dropped it, so every process took another whole-system snapshot (2.3 s for 323 processes).
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
                catch (System.ComponentModel.Win32Exception)
                {
                    // Renew al máximo (w8): a process that denies observation (another user's, a protected one: 142 of
                    // 323 on the notebook) is omitted instead of guessed, and counted so the list says it left them out.
                    denied++;
                }
                catch (Exception error) when (error is InvalidOperationException or NotSupportedException)
                {
                    // A process can exit between enumeration and measurement. It is omitted instead of guessed.
                }
                catch (OutOfMemoryException)
                {
                    // Windows can temporarily refuse another process snapshot
                    // while the local model is consuming most committed memory.
                    // Preserve the already observed, verified subset instead of
                    // failing the whole status request or repeatedly allocating, and say it is a subset.
                    complete = false;
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
