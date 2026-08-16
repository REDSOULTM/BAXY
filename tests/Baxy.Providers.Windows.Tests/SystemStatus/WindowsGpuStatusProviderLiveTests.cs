using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.SystemStatus;

[TestFixture]
public sealed class WindowsGpuStatusProviderLiveTests
{
    [Test]
    [Explicit("Physical Windows GPU/PDH validation for an authorized local host.")]
    public async Task DxgiAndPdhProduceOneCoherentLocalSnapshot()
    {
        var rawProbe = new WindowsGpuStatusProbe();
        using (IGpuStatusProbeSession session = rawProbe.OpenSession())
        {
            IReadOnlyList<GpuAdapterReading> rawAdapters = session.ReadAdapters();
            IReadOnlyList<GpuUsageReading> rawUsage = await session.ReadUsageAsync(
                rawAdapters.Select(static adapter => adapter.Key).ToArray(),
                WindowsGpuStatusProvider.DefaultSamplingInterval,
                CancellationToken.None);
            Assert.That(rawUsage, Is.Not.Empty);
            Assert.That(session.IsCurrent(), Is.True);
        }

        var provider = new WindowsGpuStatusProvider();

        GpuStatusSnapshot identity = await provider.GetStatusAsync(
            GpuStatusScope.Identity,
            CancellationToken.None);
        GpuStatusSnapshot usage = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);
        int[] unsupportedIndexes = usage.Failures
            .Where(static failure => failure.AdapterIndex.HasValue)
            .Select(static failure => failure.AdapterIndex!.Value)
            .ToArray();
        int measuredAdapters = usage.Adapters.Count(HasCompleteUsage);

        Assert.Multiple(() =>
        {
            Assert.That(identity.Failures, Is.Empty);
            Assert.That(identity.Adapters, Is.Not.Empty);
            Assert.That(usage.Adapters, Has.Count.EqualTo(identity.Adapters.Count));
            Assert.That(measuredAdapters, Is.GreaterThanOrEqualTo(1));
            Assert.That(unsupportedIndexes, Is.Unique);
            Assert.That(usage.Failures, Has.All.Matches<GpuStatusFailure>(failure =>
                failure.Scope == GpuStatusScope.Usage
                && failure.ErrorCode == SystemStatusErrorCodes.Unsupported
                && failure.AdapterIndex is >= 0
                && failure.AdapterIndex < usage.Adapters.Count));

            for (int index = 0; index < usage.Adapters.Count; index++)
            {
                GpuAdapterStatus adapter = usage.Adapters[index];
                bool isMeasured = HasCompleteUsage(adapter);
                bool hasFailure = unsupportedIndexes.Contains(index);
                Assert.That(isMeasured, Is.Not.EqualTo(hasFailure));
                Assert.That(
                    adapter.UsagePercent.HasValue,
                    Is.EqualTo(adapter.DedicatedMemoryUsageBytes.HasValue));
                Assert.That(
                    adapter.UsagePercent.HasValue,
                    Is.EqualTo(adapter.SharedMemoryUsageBytes.HasValue));
                if (isMeasured)
                {
                    Assert.That(adapter.UsagePercent, Is.InRange(0d, 100d));
                }
            }
        });

        for (int index = 0; index < usage.Adapters.Count; index++)
        {
            GpuAdapterStatus adapter = usage.Adapters[index];
            string outcome = HasCompleteUsage(adapter)
                ? $"usage={adapter.UsagePercent:0.###} %, "
                    + $"dedicated={adapter.DedicatedMemoryUsageBytes} B, "
                    + $"shared={adapter.SharedMemoryUsageBytes} B"
                : $"usage={usage.Failures.Single(failure => failure.AdapterIndex == index).ErrorCode}";
            TestContext.Out.WriteLine(
                $"{adapter.Name}: {outcome}, "
                + $"dedicatedVideo={adapter.DedicatedVideoMemoryBytes} B, "
                + $"dedicatedSystem={adapter.DedicatedSystemMemoryBytes} B, "
                + $"sharedLimit={adapter.SharedSystemMemoryLimitBytes} B");
        }
    }

    private static bool HasCompleteUsage(GpuAdapterStatus adapter) =>
        adapter.UsagePercent.HasValue
        && adapter.DedicatedMemoryUsageBytes.HasValue
        && adapter.SharedMemoryUsageBytes.HasValue;
}
