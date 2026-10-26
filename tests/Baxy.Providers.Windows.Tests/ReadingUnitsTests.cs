using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Holdout v4 (falsedad): «69 % de CPU» was said where the reading was 0.69 %. The readings of the PC go with their unit
/// written beside the number, as a person reads them in Spanish.
/// </summary>
[TestFixture]
public sealed class ReadingUnitsTests
{
    [TestCase(0.6923, "0,69 %")]
    [TestCase(69, "69 %")]
    [TestCase(12.345, "12,35 %")]
    [TestCase(100, "100 %")]
    [TestCase(0, "0 %")]
    [TestCase(0.001, "menos de 0,01 %")]
    public void APercentageIsWrittenOnItsOwnScaleWithItsUnit(double percent, string written) =>
        Assert.That(ReadingUnits.Percent(percent), Is.EqualTo(written));

    [TestCase(512d, "512 bytes")]
    [TestCase(1536d, "1,5 KB")]
    [TestCase(34_037_329_920d, "31,7 GB")]
    [TestCase(2_199_023_255_552d, "2 TB")]
    public void ASizeIsWrittenInTheLargestUnitOf1024ItReaches(double bytes, string written) =>
        Assert.That(ReadingUnits.Size(bytes), Is.EqualTo(written));

    [Test]
    public async Task TheStatusOfThePcSaysEachReadingWithItsUnit()
    {
        var handler = new SystemStatusHandler(new FixedSystem(), new NoGpu(), new NoSecurity());

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"scope\":\"summary\"}").RootElement),
            CancellationToken.None);

        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        JsonElement result = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("cpu").GetProperty("usagePercent").GetDouble(), Is.EqualTo(0.6923));
            Assert.That(result.GetProperty("cpu").GetProperty("usage").GetString(), Is.EqualTo("0,69 %"));
            JsonElement memory = result.GetProperty("memory");
            Assert.That(memory.GetProperty("total").GetString(), Is.EqualTo("32 GB"));
            Assert.That(memory.GetProperty("available").GetString(), Is.EqualTo("8 GB"));
            Assert.That(memory.GetProperty("inUse").GetString(), Is.EqualTo("24 GB"));
            Assert.That(memory.GetProperty("inUseShare").GetString(), Is.EqualTo("75 %"));
            JsonElement disk = result.GetProperty("disk");
            Assert.That(disk.GetProperty("total").GetString(), Is.EqualTo("1 TB"));
            Assert.That(disk.GetProperty("available").GetString(), Is.EqualTo("256 GB"));
            Assert.That(disk.GetProperty("inUseShare").GetString(), Is.EqualTo("75 %"));
            Assert.That(result.GetProperty("battery").GetProperty("charge").GetString(), Is.EqualTo("85 %"));
        });
    }

    [Test]
    public async Task AProcessSaysItsShareOfTheCpuAndItsMemoryWithTheirUnits()
    {
        var handler = new ProcessListHandler(new FixedProcesses());

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"sort\":\"cpu\",\"limit\":1}").RootElement),
            CancellationToken.None);

        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        JsonElement process = outcome.Result!.Value.GetProperty("processes")[0];
        Assert.Multiple(() =>
        {
            Assert.That(process.GetProperty("cpuUsagePercent").GetDouble(), Is.EqualTo(0.69));
            Assert.That(process.GetProperty("cpuUsage").GetString(), Is.EqualTo("0,69 %"));
            Assert.That(process.GetProperty("workingSet").GetString(), Is.EqualTo("150 MB"));
        });
    }

    private const ulong GiB = 1024UL * 1024 * 1024;

    private sealed class FixedSystem : ISystemStatusProvider
    {
        public ValueTask<SystemStatusSnapshot> GetStatusAsync(SystemStatusScope scope, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new SystemStatusSnapshot(
                scope.HasFlag(SystemStatusScope.Cpu) ? new CpuStatus(0.6923, 16, "CPU", 8) : null,
                scope.HasFlag(SystemStatusScope.Memory) ? new MemoryStatus(32 * GiB, 8 * GiB) : null,
                scope.HasFlag(SystemStatusScope.SystemDisk) ? new SystemDiskStatus(1024L * (long)GiB, 256L * (long)GiB) : null,
                scope.HasFlag(SystemStatusScope.Battery) ? new BatteryStatus(true, 85, false, true) : null,
                scope.HasFlag(SystemStatusScope.OperatingSystem)
                    ? new OperatingSystemStatus(10, 0, 26100, "x64", true, "Windows 11") : null,
                scope.HasFlag(SystemStatusScope.Uptime) ? 3_600 : null,
                []));
    }

    private sealed class FixedProcesses : IProcessStatusProvider
    {
        public ValueTask<ProcessStatusSnapshot> GetProcessesAsync(
            ProcessStatusSort sort, int limit, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ProcessStatusSnapshot(
                40, [new ProcessStatusEntry(4242, 638_000_000_000_000_000, "steam", 150L * 1024 * 1024, 69.3, 0.69, 1.0)], 16));
    }

    private sealed class NoGpu : IGpuStatusProvider
    {
        public ValueTask<GpuStatusSnapshot> GetStatusAsync(GpuStatusScope scope, CancellationToken cancellationToken) =>
            throw new AssertionException("the GPU is not read for this scope");
    }

    private sealed class NoSecurity : ISecurityStatusProvider
    {
        public ValueTask<SecurityStatusReading> ReadAsync(string scope, CancellationToken cancellationToken) =>
            throw new AssertionException("security is not read for this scope");
    }
}
