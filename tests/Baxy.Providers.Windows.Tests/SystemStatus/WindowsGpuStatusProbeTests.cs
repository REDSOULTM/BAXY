using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.SystemStatus;

[TestFixture]
public sealed class WindowsGpuStatusProbeTests
{
    private static readonly GpuAdapterKey Primary = new(0x0001A503, 0);
    private static readonly GpuAdapterKey Secondary = new(0x0001B974, 0);

    [Test]
    public void EngineContributionsAreSummedPerEngineThenMaxedPerAdapter()
    {
        WindowsGpuStatusProbe.PdhValue[] engines =
        [
            Engine(100, Primary, physical: 0, engine: 0, "3D", 20),
            Engine(200, Primary, physical: 0, engine: 0, "3D", 15),
            Engine(100, Primary, physical: 0, engine: 2, "VideoDecode", 60),
            Engine(300, Secondary, physical: 0, engine: 1, "Copy#1", 7.5),
            Engine(400, new GpuAdapterKey(999, 0), 0, 0, "3D", 99),
        ];
        WindowsGpuStatusProbe.PdhValue[] dedicated =
        [
            Memory(Primary, 0, 1_000),
            Memory(Secondary, 0, 2_000),
        ];
        WindowsGpuStatusProbe.PdhValue[] shared =
        [
            Memory(Primary, 0, 300),
            Memory(Secondary, 0, 400),
        ];

        IReadOnlyList<GpuUsageReading> result = WindowsGpuStatusProbe.AggregateUsage(
            [Primary, Secondary],
            engines,
            dedicated,
            shared);

        Assert.Multiple(() =>
        {
            Assert.That(result, Has.Count.EqualTo(2));
            Assert.That(result[0], Is.EqualTo(new GpuUsageReading(Primary, 60, 1_000, 300)));
            Assert.That(result[1], Is.EqualTo(new GpuUsageReading(Secondary, 7.5, 2_000, 400)));
        });
    }

    [Test]
    public void AdapterWithMemoryButNoEngineInstanceIsReportedAsIdle()
    {
        IReadOnlyList<GpuUsageReading> result = WindowsGpuStatusProbe.AggregateUsage(
            [Primary, Secondary],
            [Engine(100, Primary, 0, 0, "3D", 12)],
            [Memory(Primary, 0, 1), Memory(Secondary, 0, 2)],
            [Memory(Primary, 0, 3), Memory(Secondary, 0, 4)]);

        Assert.That(result[1], Is.EqualTo(new GpuUsageReading(Secondary, 0, 2, 4)));
    }

    [Test]
    public void AdapterWithoutACompleteMemoryPairIsOmittedWithoutDiscardingMeasuredAdapters()
    {
        IReadOnlyList<GpuUsageReading> result = WindowsGpuStatusProbe.AggregateUsage(
            [Primary, Secondary],
            [
                Engine(100, Primary, 0, 0, "3D", 12),
                Engine(200, Secondary, 0, 0, "3D", 34),
            ],
            [Memory(Primary, 0, 10), Memory(Secondary, 0, 20)],
            [Memory(Secondary, 0, 30)]);

        Assert.That(
            result,
            Is.EqualTo(new[] { new GpuUsageReading(Secondary, 34, 20, 30) }));
    }

    [Test]
    public void PhysicalMemoryInstancesAreSummedCheckedWithinOneAdapterOnly()
    {
        IReadOnlyList<GpuUsageReading> result = WindowsGpuStatusProbe.AggregateUsage(
            [Primary, Secondary],
            [Engine(100, Primary, 0, 0, "3D", 10)],
            [
                Memory(Primary, 0, 100),
                Memory(Primary, 1, 200, suffix: "#1"),
                Memory(Secondary, 0, 1_000),
            ],
            [
                Memory(Primary, 0, 30),
                Memory(Primary, 1, 40),
                Memory(Secondary, 0, 2_000),
            ]);

        Assert.Multiple(() =>
        {
            Assert.That(result[0].DedicatedMemoryUsageBytes, Is.EqualTo(300));
            Assert.That(result[0].SharedMemoryUsageBytes, Is.EqualTo(70));
            Assert.That(result[1].DedicatedMemoryUsageBytes, Is.EqualTo(1_000));
            Assert.That(result[1].SharedMemoryUsageBytes, Is.EqualTo(2_000));
        });
    }

    [Test]
    public void MalformedInstancesInvalidateTheSnapshotInsteadOfBeingSilentlyDropped()
    {
        WindowsGpuStatusProbe.PdhValue[] malformed =
        [
            new("not-a-gpu-instance", 100, 100),
            new("pid_1_luid_0x00000000_0x0001A503_phys_0_eng_bad_engtype_3D", 100, 100),
        ];

        Assert.That(
            () => WindowsGpuStatusProbe.AggregateUsage(
                [Primary],
                malformed,
                [Memory(Primary, 0, 1)],
                [Memory(Primary, 0, 1)]),
            Throws.TypeOf<GpuInvalidMeasurementException>());
    }

    [Test]
    public void WellFormedUnknownWildcardAdaptersDoNotContaminateAKnownAdapter()
    {
        GpuAdapterKey unknown = new(0x0000B949, 0);
        IReadOnlyList<GpuUsageReading> result = WindowsGpuStatusProbe.AggregateUsage(
            [Primary],
            [
                Engine(200, unknown, 0, 0, "3D", 88),
                Engine(100, Primary, 0, 0, "3D", 12),
            ],
            [
                Memory(unknown, 0, 888),
                Memory(Primary, 0, 10),
            ],
            [Memory(unknown, 0, 777), Memory(Primary, 0, 20)]);

        Assert.That(
            result,
            Is.EqualTo(new[] { new GpuUsageReading(Primary, 12, 10, 20) }));
    }

    [Test]
    public void EngineSumAbovePhysicalMaximumFailsClosed()
    {
        Assert.That(
            () => WindowsGpuStatusProbe.AggregateUsage(
                [Primary],
                [
                    Engine(100, Primary, 0, 0, "3D", 60),
                    Engine(200, Primary, 0, 0, "3D", 41),
                ],
                [Memory(Primary, 0, 1)],
                [Memory(Primary, 0, 1)]),
            Throws.TypeOf<GpuInvalidMeasurementException>());
    }

    [Test]
    public void MissingOrNegativeMemoryCountersFailClosed()
    {
        WindowsGpuStatusProbe.PdhValue engine = Engine(100, Primary, 0, 0, "3D", 1);
        Assert.Multiple(() =>
        {
            Assert.That(
                () => WindowsGpuStatusProbe.AggregateUsage(
                    [Primary],
                    [engine],
                    [],
                    [Memory(Primary, 0, 1)]),
                Throws.InstanceOf<PlatformNotSupportedException>());
            Assert.That(
                () => WindowsGpuStatusProbe.AggregateUsage(
                    [Primary],
                    [engine],
                    [Memory(Primary, 0, -1)],
                    [Memory(Primary, 0, 1)]),
                Throws.TypeOf<GpuInvalidMeasurementException>());
        });
    }

    [Test]
    public void DuplicateAdapterKeysAreRejectedBeforeAggregation()
    {
        Assert.That(
            () => WindowsGpuStatusProbe.AggregateUsage(
                [Primary, Primary],
                [],
                [],
                []),
            Throws.TypeOf<GpuInvalidMeasurementException>());
    }

    [Test]
    public void EmptySuccessfulCounterHandleIsAnInvalidMeasurement()
    {
        Assert.That(
            () => WindowsGpuStatusProbe.ValidateCounterHandle(0, 0),
            Throws.TypeOf<GpuInvalidMeasurementException>());
    }

    [TestCase(0xC0000BB8u)]
    [TestCase(0xC0000BB9u)]
    [TestCase(0xC0000BBFu)]
    [TestCase(0xC0000BC0u)]
    public void MissingCounterStatusesAreUnsupported(uint status)
    {
        Assert.That(
            () => WindowsGpuStatusProbe.ValidateCounterHandle(status, 0),
            Throws.TypeOf<PlatformNotSupportedException>());
    }

    [Test]
    public void NativeCounterFailureIsNotMisclassifiedAsUnsupported()
    {
        Assert.That(
            () => WindowsGpuStatusProbe.ValidateCounterHandle(0xC0000BDBu, 0),
            Throws.TypeOf<System.ComponentModel.Win32Exception>());
    }

    [TestCase(64u, 65u, 1u, 24u)]
    [TestCase(64u, 64u, 3u, 24u)]
    [TestCase(64u, 64u, 1u, 0u)]
    [TestCase(128u, 119u, 5u, 24u)]
    [TestCase(128u, 0u, 1u, 24u)]
    public void CounterArrayCannotEscapeItsAllocatedNativeBuffer(
        uint allocatedBytes,
        uint reportedBytes,
        uint itemCount,
        uint itemBytes)
    {
        Assert.That(
            () => WindowsGpuStatusProbe.ValidateCounterArrayBounds(
                allocatedBytes,
                reportedBytes,
                itemCount,
                itemBytes),
            Throws.TypeOf<InvalidOperationException>());
    }

    [Test]
    public void CounterArrayBoundsAcceptAContainedNativeLayout()
    {
        Assert.That(
            () => WindowsGpuStatusProbe.ValidateCounterArrayBounds(
                allocatedBufferSize: 128,
                reportedBufferSize: 120,
                itemCount: 5,
                nativeItemSize: 24),
            Throws.Nothing);
    }

    private static WindowsGpuStatusProbe.PdhValue Engine(
        int processId,
        GpuAdapterKey adapter,
        uint physical,
        uint engine,
        string engineType,
        double value) => new(
            $"pid_{processId}_luid_0x{unchecked((uint)adapter.HighPart):X8}_"
            + $"0x{adapter.LowPart:X8}_phys_{physical}_eng_{engine}_engtype_{engineType}",
            value,
            checked((long)value));

    private static WindowsGpuStatusProbe.PdhValue Memory(
        GpuAdapterKey adapter,
        uint physical,
        long value,
        string suffix = "") => new(
            $"luid_0x{unchecked((uint)adapter.HighPart):X8}_0x{adapter.LowPart:X8}_"
            + $"phys_{physical}{suffix}",
            value,
            value);
}
