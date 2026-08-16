using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

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
}
