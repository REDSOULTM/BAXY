using System.Diagnostics;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;
using static Baxy.Providers.Windows.SystemStatus.WindowsProcessStatusProvider;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsProcessStatusProviderTests
{
    [TestCase(ProcessStatusSort.Cpu)]
    [TestCase(ProcessStatusSort.Memory)]
    [TestCase(ProcessStatusSort.Name)]
    public async Task LiveInventoryReturnsBoundedTwiceObservedIdentities(
        ProcessStatusSort sort)
    {
        var provider = new WindowsProcessStatusProvider();

        ProcessStatusSnapshot snapshot = await provider.GetProcessesAsync(
            sort,
            5,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.ObservedProcessCount, Is.GreaterThan(0));
            Assert.That(snapshot.Processes, Is.Not.Empty);
            Assert.That(snapshot.Processes, Has.Count.LessThanOrEqualTo(5));
            if (sort == ProcessStatusSort.Cpu)
            {
                Assert.That(snapshot.LogicalProcessorCount, Is.GreaterThan(0));
                Assert.That(snapshot.Processes.All(static item =>
                    item.CpuUsagePercent is >= 0 and <= 100
                    && item.SampleDurationSeconds >= 0.15), Is.True);
            }
            Assert.That(snapshot.Processes.All(static item =>
                item.ProcessId > 0
                && item.CreationTimeUtcTicks > 0
                && !string.IsNullOrWhiteSpace(item.Name)
                && item.WorkingSetBytes >= 0
                && double.IsFinite(item.TotalProcessorSeconds)
                && item.TotalProcessorSeconds >= 0), Is.True);
            Assert.That(
                snapshot.Processes
                    .Select(static item => (item.ProcessId, item.CreationTimeUtcTicks))
                    .Distinct()
                    .Count(),
                Is.EqualTo(snapshot.Processes.Count));
        });
    }

    [Test]
    public void CpuRanksRecentActivityInsteadOfLifetimeAndNormalizesToMachine()
    {
        var first = new Dictionary<ProcessIdentity, ProcessSample>([
            Sample(101, 1, "old-idle", 9000, 10),
            Sample(202, 2, "new-busy", 1, 12),
            Sample(303, 3, "medium", 500, 10),
        ]);
        var second = new Dictionary<ProcessIdentity, ProcessSample>([
            Sample(101, 1, "old-idle", 9000, 12),
            Sample(202, 2, "new-busy", 5, 13),
            Sample(303, 3, "medium", 502, 12),
        ]);

        ProcessStatusSnapshot result = CreateSnapshot(first, second, ProcessStatusSort.Cpu, 2, 8);

        Assert.Multiple(() =>
        {
            Assert.That(result.ObservedProcessCount, Is.EqualTo(3));
            Assert.That(result.Processes.Select(static item => item.ProcessId), Is.EqualTo(new[] { 202, 303 }));
            Assert.That(result.Processes[0].CpuUsagePercent, Is.EqualTo(50));
            Assert.That(result.Processes[0].SampleDurationSeconds, Is.EqualTo(1));
            Assert.That(result.Processes[1].CpuUsagePercent, Is.EqualTo(12.5));
            Assert.That(result.Processes[1].SampleDurationSeconds, Is.EqualTo(2));
        });
    }

    [Test]
    public void ReusedPidAndInvalidDeltasCannotEnterCpuRanking()
    {
        var first = new Dictionary<ProcessIdentity, ProcessSample>([
            Sample(101, 1, "reused", 100, 10),
            Sample(202, 2, "rollback", 100, 10),
            Sample(303, 3, "no-time", 100, 10),
            Sample(404, 4, "valid", 100, 10),
        ]);
        var second = new Dictionary<ProcessIdentity, ProcessSample>([
            Sample(101, 5, "reused", 1, 11),
            Sample(202, 2, "rollback", 99, 11),
            Sample(303, 3, "no-time", 101, 10),
            Sample(404, 4, "valid", 101, 11),
        ]);

        ProcessStatusSnapshot result = CreateSnapshot(first, second, ProcessStatusSort.Cpu, 5, 8);

        Assert.That(result.Processes.Select(static item => item.ProcessId), Is.EqualTo(new[] { 404 }));
    }

    [Test]
    public void CancelledRequestDoesNotObserveProcesses()
    {
        var provider = new WindowsProcessStatusProvider();
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        Assert.ThrowsAsync<OperationCanceledException>(async () =>
            await provider.GetProcessesAsync(ProcessStatusSort.Cpu, 5, cancellation.Token));
    }

    private static KeyValuePair<ProcessIdentity, ProcessSample> Sample(
        int pid, long created, string name, double cpuSeconds, long wallSeconds) => new(
            new ProcessIdentity(pid, created, name),
            new ProcessSample(new ProcessStatusEntry(pid, created, name, 1024, cpuSeconds),
                wallSeconds * Stopwatch.Frequency));
}
