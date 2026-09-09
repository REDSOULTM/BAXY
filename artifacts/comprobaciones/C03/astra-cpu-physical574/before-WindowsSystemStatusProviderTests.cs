using System.Reflection;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsSystemStatusProviderTests
{
    private const ulong Gibibyte = 1024UL * 1024 * 1024;

    [Test]
    public async Task FullSnapshotReturnsOnlyCorroboratedMeasurements()
    {
        var probe = new FakeSystemStatusProbe
        {
            LogicalProcessorCount = 16,
            CpuModel = "  Example CPU  ",
            Memory = new MemoryReading(32 * Gibibyte, 12 * Gibibyte),
            Disk = new DiskReading(512L * (long)Gibibyte, 123L * (long)Gibibyte),
            Power = new PowerReading(1, 0x08, 77),
            OperatingSystem = new OperatingSystemReading(10, 0, 26100, "x64", true, "Microsoft Windows 11 Pro"),
            UptimeMilliseconds = 9_876_543,
        };
        probe.CpuSamples.Enqueue(new CpuTimeSample(100, 300, 100));
        probe.CpuSamples.Enqueue(new CpuTimeSample(140, 380, 140));
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.All,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Failures, Is.Empty);
            Assert.That(snapshot.Cpu, Is.Not.Null);
            Assert.That(snapshot.Cpu!.UsagePercent, Is.EqualTo(66.6666666667d).Within(0.000001d));
            Assert.That(snapshot.Cpu.LogicalProcessorCount, Is.EqualTo(16));
            Assert.That(snapshot.Cpu.Model, Is.EqualTo("Example CPU"));
            Assert.That(snapshot.Memory, Is.EqualTo(new MemoryStatus(32 * Gibibyte, 12 * Gibibyte)));
            Assert.That(
                snapshot.SystemDisk,
                Is.EqualTo(new SystemDiskStatus(
                    512L * (long)Gibibyte,
                    123L * (long)Gibibyte)));
            Assert.That(snapshot.Battery, Is.EqualTo(new BatteryStatus(true, 77, true, true)));
            Assert.That(
                snapshot.OperatingSystem,
                Is.EqualTo(new OperatingSystemStatus(10, 0, 26100, "x64", true, "Microsoft Windows 11 Pro")));
            Assert.That(snapshot.UptimeSeconds, Is.EqualTo(9_876));
            Assert.That(probe.DelayCalls, Is.EqualTo(1));
            Assert.That(probe.LastDelay, Is.EqualTo(TimeSpan.FromMilliseconds(10)));
        });
    }

    [Test]
    public async Task ScopeDoesNotProbeOrReturnUnrequestedHostData()
    {
        var probe = new FakeSystemStatusProbe
        {
            Memory = new MemoryReading(16 * Gibibyte, 4 * Gibibyte),
            UptimeMilliseconds = 4_321_000,
        };
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Memory | SystemStatusScope.Uptime,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Memory, Is.Not.Null);
            Assert.That(snapshot.UptimeSeconds, Is.EqualTo(4_321));
            Assert.That(snapshot.Cpu, Is.Null);
            Assert.That(snapshot.SystemDisk, Is.Null);
            Assert.That(snapshot.Battery, Is.Null);
            Assert.That(snapshot.OperatingSystem, Is.Null);
            Assert.That(snapshot.Failures, Is.Empty);
            Assert.That(probe.CpuTimeCalls, Is.Zero);
            Assert.That(probe.DiskCalls, Is.Zero);
            Assert.That(probe.PowerCalls, Is.Zero);
            Assert.That(probe.OperatingSystemCalls, Is.Zero);
        });
    }

    [Test]
    public async Task DesktopWithoutBatteryIsAValidMeasurementRatherThanAFailure()
    {
        var probe = new FakeSystemStatusProbe
        {
            Power = new PowerReading(
                AcLineStatus: 1,
                BatteryFlag: 0x80,
                BatteryLifePercent: byte.MaxValue),
        };
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Battery,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Failures, Is.Empty);
            Assert.That(snapshot.Battery, Is.Not.Null);
            Assert.That(snapshot.Battery!.IsPresent, Is.False);
            Assert.That(snapshot.Battery.ChargePercent, Is.Null);
            Assert.That(snapshot.Battery.IsCharging, Is.Null);
            Assert.That(snapshot.Battery.IsAcOnline, Is.True);
        });
    }

    [Test]
    public async Task FullyUnknownPowerStatusBecomesAPartialFailureWithoutErasingMemory()
    {
        var probe = new FakeSystemStatusProbe
        {
            Memory = new MemoryReading(16 * Gibibyte, 4 * Gibibyte),
            Power = new PowerReading(
                AcLineStatus: byte.MaxValue,
                BatteryFlag: byte.MaxValue,
                BatteryLifePercent: byte.MaxValue),
        };
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Memory | SystemStatusScope.Battery,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Memory, Is.EqualTo(new MemoryStatus(16 * Gibibyte, 4 * Gibibyte)));
            Assert.That(snapshot.Battery, Is.Null);
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new SystemStatusFailure(
                        SystemStatusScope.Battery,
                        SystemStatusErrorCodes.InvalidMeasurement),
                }));
        });
    }

    [TestCase(100UL, 300UL, 100UL, 99UL, 380UL, 140UL)]
    [TestCase(100UL, 300UL, 100UL, 100UL, 300UL, 100UL)]
    [TestCase(100UL, 300UL, 100UL, 500UL, 350UL, 110UL)]
    [TestCase(0UL, 0UL, 0UL, 0UL, ulong.MaxValue, 1UL)]
    public async Task InvalidCpuDeltasFailThatMetricWithoutNaN(
        ulong firstIdle,
        ulong firstKernel,
        ulong firstUser,
        ulong secondIdle,
        ulong secondKernel,
        ulong secondUser)
    {
        var probe = new FakeSystemStatusProbe();
        probe.CpuSamples.Enqueue(new CpuTimeSample(firstIdle, firstKernel, firstUser));
        probe.CpuSamples.Enqueue(new CpuTimeSample(secondIdle, secondKernel, secondUser));
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Cpu,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Cpu, Is.Null);
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new SystemStatusFailure(
                        SystemStatusScope.Cpu,
                        SystemStatusErrorCodes.InvalidMeasurement),
                }));
        });
    }

    [Test]
    public async Task InvalidLogicalProcessorCountFailsCpuMetric()
    {
        var probe = ValidCpuProbe();
        probe.LogicalProcessorCount = 0;
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Cpu,
            CancellationToken.None);

        Assert.That(snapshot.Cpu, Is.Null);
        Assert.That(
            snapshot.Failures.Single(),
            Is.EqualTo(new SystemStatusFailure(
                SystemStatusScope.Cpu,
                SystemStatusErrorCodes.InvalidMeasurement)));
    }

    [Test]
    public async Task UnreliableCpuModelIsOmittedWithoutDiscardingMeasuredCpuData()
    {
        string[] unreliableModels =
        {
            "not reliable\u0000value",
            new('\uD800', 1),
        };

        foreach (string unreliableModel in unreliableModels)
        {
            FakeSystemStatusProbe probe = ValidCpuProbe();
            probe.CpuModel = unreliableModel;
            var provider = CreateProvider(probe);

            SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
                SystemStatusScope.Cpu,
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(snapshot.Failures, Is.Empty);
                Assert.That(snapshot.Cpu, Is.Not.Null);
                Assert.That(snapshot.Cpu!.Model, Is.Null);
                Assert.That(double.IsFinite(snapshot.Cpu.UsagePercent), Is.True);
            });
        }
    }

    [Test]
    public async Task PartialProbeFailureDoesNotLeakItsMessageOrEraseValidMetrics()
    {
        const string sensitiveMessage = @"user@example.invalid 192.0.2.44 C:\Users\Private";
        var probe = new FakeSystemStatusProbe
        {
            MemoryException = new IOException(sensitiveMessage),
            Disk = new DiskReading(1000, 400),
        };
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Memory | SystemStatusScope.SystemDisk,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Memory, Is.Null);
            Assert.That(snapshot.SystemDisk, Is.EqualTo(new SystemDiskStatus(1000, 400)));
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new SystemStatusFailure(
                        SystemStatusScope.Memory,
                        SystemStatusErrorCodes.MeasurementFailed),
                }));
            Assert.That(snapshot.ToString(), Does.Not.Contain(sensitiveMessage));
            Assert.That(snapshot.ToString(), Does.Not.Contain("192.0.2.44"));
            Assert.That(snapshot.ToString(), Does.Not.Contain("Private"));
        });
    }

    [Test]
    public async Task UnsupportedAndInvalidSectionsHaveDistinctSanitizedFailures()
    {
        var probe = new FakeSystemStatusProbe
        {
            OperatingSystemException = new PlatformNotSupportedException("private detail"),
            Memory = new MemoryReading(0, 0),
        };
        var provider = CreateProvider(probe);

        SystemStatusSnapshot snapshot = await provider.GetStatusAsync(
            SystemStatusScope.Memory | SystemStatusScope.OperatingSystem,
            CancellationToken.None);

        Assert.That(
            snapshot.Failures,
            Is.EqualTo(new[]
            {
                new SystemStatusFailure(
                    SystemStatusScope.Memory,
                    SystemStatusErrorCodes.InvalidMeasurement),
                new SystemStatusFailure(
                    SystemStatusScope.OperatingSystem,
                    SystemStatusErrorCodes.Unsupported),
            }));
    }

    [Test]
    public void CancellationBeforeCollectionDoesNotTouchTheHost()
    {
        var probe = new FakeSystemStatusProbe();
        var provider = CreateProvider(probe);
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();

        Assert.That(
            async () => await provider.GetStatusAsync(SystemStatusScope.All, cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(probe.TotalCalls, Is.Zero);
    }

    [Test]
    public async Task CancellationDuringCpuSamplingStopsBeforeTheSecondSample()
    {
        var enteredDelay = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var probe = new FakeSystemStatusProbe
        {
            Delay = async (_, cancellationToken) =>
            {
                enteredDelay.TrySetResult();
                await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
            },
        };
        probe.CpuSamples.Enqueue(new CpuTimeSample(100, 300, 100));
        var provider = CreateProvider(probe);
        using var cancellation = new CancellationTokenSource();

        Task<SystemStatusSnapshot> pending = provider.GetStatusAsync(
            SystemStatusScope.Cpu,
            cancellation.Token).AsTask();
        await enteredDelay.Task;
        cancellation.Cancel();

        Assert.That(
            async () => await pending,
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(probe.CpuTimeCalls, Is.EqualTo(1));
    }

    [TestCase(SystemStatusScope.None)]
    [TestCase((SystemStatusScope)(1 << 20))]
    public void InvalidScopeIsRejectedBeforeCollection(SystemStatusScope scope)
    {
        var probe = new FakeSystemStatusProbe();
        var provider = CreateProvider(probe);

        Assert.That(
            async () => await provider.GetStatusAsync(scope, CancellationToken.None),
            Throws.TypeOf<ArgumentOutOfRangeException>());
        Assert.That(probe.TotalCalls, Is.Zero);
    }

    [Test]
    public void PublicStatusContractContainsNoNetworkUserOrProcessInventoryFields()
    {
        Type[] contractTypes =
        [
            typeof(CpuStatus),
            typeof(MemoryStatus),
            typeof(SystemDiskStatus),
            typeof(BatteryStatus),
            typeof(OperatingSystemStatus),
            typeof(SystemStatusFailure),
            typeof(SystemStatusSnapshot),
        ];
        string[] forbiddenNames =
        [
            "HostName",
            "UserName",
            "IpAddress",
            "MacAddress",
            "Processes",
            "ProcessIds",
            "RootPath",
        ];

        string[] propertyNames = contractTypes
            .SelectMany(static type => type.GetProperties(BindingFlags.Instance | BindingFlags.Public))
            .Select(static property => property.Name)
            .ToArray();

        Assert.That(propertyNames, Has.None.Matches<string>(forbiddenNames.Contains));
    }

    private static WindowsSystemStatusProvider CreateProvider(FakeSystemStatusProbe probe) =>
        new(probe, TimeSpan.FromMilliseconds(10));

    private static FakeSystemStatusProbe ValidCpuProbe()
    {
        var probe = new FakeSystemStatusProbe();
        probe.CpuSamples.Enqueue(new CpuTimeSample(100, 300, 100));
        probe.CpuSamples.Enqueue(new CpuTimeSample(125, 350, 125));
        return probe;
    }

    private sealed class FakeSystemStatusProbe : ISystemStatusProbe
    {
        public Queue<CpuTimeSample> CpuSamples { get; } = new();

        public int LogicalProcessorCount { get; set; } = 8;

        public string? CpuModel { get; set; } = "Example CPU";

        public MemoryReading Memory { get; set; } = new(16 * Gibibyte, 8 * Gibibyte);

        public DiskReading Disk { get; set; } = new(256L * (long)Gibibyte, 64L * (long)Gibibyte);

        public PowerReading Power { get; set; } = new(1, 0, 50);

        public OperatingSystemReading OperatingSystem { get; set; } =
            new(10, 0, 26100, "x64", true, "Microsoft Windows 11 Pro");

        public ulong UptimeMilliseconds { get; set; } = 1_000;

        public Exception? CpuException { get; set; }

        public Exception? MemoryException { get; set; }

        public Exception? DiskException { get; set; }

        public Exception? PowerException { get; set; }

        public Exception? OperatingSystemException { get; set; }

        public Exception? UptimeException { get; set; }

        public Func<TimeSpan, CancellationToken, ValueTask>? Delay { get; set; }

        public int CpuTimeCalls { get; private set; }

        public int DelayCalls { get; private set; }

        public int MemoryCalls { get; private set; }

        public int DiskCalls { get; private set; }

        public int PowerCalls { get; private set; }

        public int OperatingSystemCalls { get; private set; }

        public int UptimeCalls { get; private set; }

        public TimeSpan LastDelay { get; private set; }

        public int TotalCalls => CpuTimeCalls
            + DelayCalls
            + MemoryCalls
            + DiskCalls
            + PowerCalls
            + OperatingSystemCalls
            + UptimeCalls;

        public CpuTimeSample ReadCpuTimes()
        {
            CpuTimeCalls++;
            if (CpuException is not null)
            {
                throw CpuException;
            }

            return CpuSamples.Dequeue();
        }

        public int ReadLogicalProcessorCount() => LogicalProcessorCount;

        public string? ReadCpuModel() => CpuModel;

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            DelayCalls++;
            LastDelay = delay;
            return Delay is null
                ? ValueTask.CompletedTask
                : Delay(delay, cancellationToken);
        }

        public MemoryReading ReadMemory()
        {
            MemoryCalls++;
            if (MemoryException is not null)
            {
                throw MemoryException;
            }

            return Memory;
        }

        public DiskReading ReadSystemDisk()
        {
            DiskCalls++;
            if (DiskException is not null)
            {
                throw DiskException;
            }

            return Disk;
        }

        public PowerReading ReadPowerStatus()
        {
            PowerCalls++;
            if (PowerException is not null)
            {
                throw PowerException;
            }

            return Power;
        }

        public ValueTask<OperatingSystemReading> ReadOperatingSystemAsync(CancellationToken cancellationToken)
        {
            OperatingSystemCalls++;
            if (OperatingSystemException is not null)
            {
                throw OperatingSystemException;
            }

            return ValueTask.FromResult(OperatingSystem);
        }

        public ulong ReadUptimeMilliseconds()
        {
            UptimeCalls++;
            if (UptimeException is not null)
            {
                throw UptimeException;
            }

            return UptimeMilliseconds;
        }
    }
}
