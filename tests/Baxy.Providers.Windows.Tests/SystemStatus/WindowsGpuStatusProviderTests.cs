using System.Reflection;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.SystemStatus;

[TestFixture]
public sealed class WindowsGpuStatusProviderTests
{
    private const ulong Gibibyte = 1024UL * 1024 * 1024;
    private static readonly GpuAdapterKey PrimaryKey = new(0x0001A503, 0);
    private static readonly GpuAdapterKey SecondaryKey = new(0x0001B974, 0);

    [Test]
    public async Task IdentityScopeReturnsBoundedCapacityWithoutSamplingUsage()
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters =
            [
                Adapter(PrimaryKey, "  NVIDIA Example  ", 16 * Gibibyte, 0, 32 * Gibibyte),
            ],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Identity,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Failures, Is.Empty);
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(1));
            Assert.That(snapshot.Adapters[0], Is.EqualTo(new GpuAdapterStatus(
                "NVIDIA Example",
                0x10DE,
                0x2803,
                16 * Gibibyte,
                0,
                32 * Gibibyte,
                null,
                null,
                null)));
            Assert.That(probe.AdapterCalls, Is.EqualTo(1));
            Assert.That(probe.UsageCalls, Is.Zero);
        });
    }

    [Test]
    public async Task UsageScopeCorrelatesEveryAdapterByLuidWithoutSummingAdapters()
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters =
            [
                Adapter(PrimaryKey, "Discrete", 16 * Gibibyte, 0, 32 * Gibibyte),
                Adapter(SecondaryKey, "Integrated", 0, 128 * 1024 * 1024, 32 * Gibibyte),
            ],
            Usage =
            [
                new GpuUsageReading(SecondaryKey, 7.5, 64 * 1024 * 1024, 512 * 1024 * 1024),
                new GpuUsageReading(PrimaryKey, 42.25, 3 * Gibibyte, 128 * 1024 * 1024),
            ],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Failures, Is.Empty);
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(2));
            Assert.That(snapshot.Adapters[0].Name, Is.EqualTo("Discrete"));
            Assert.That(snapshot.Adapters[0].UsagePercent, Is.EqualTo(42.25));
            Assert.That(
                snapshot.Adapters[0].DedicatedMemoryUsageBytes,
                Is.EqualTo(3 * Gibibyte));
            Assert.That(
                snapshot.Adapters[0].SharedMemoryUsageBytes,
                Is.EqualTo(128 * 1024 * 1024));
            Assert.That(snapshot.Adapters[1].Name, Is.EqualTo("Integrated"));
            Assert.That(snapshot.Adapters[1].UsagePercent, Is.EqualTo(7.5));
            Assert.That(probe.LastSamplingInterval, Is.EqualTo(TimeSpan.FromMilliseconds(10)));
            Assert.That(probe.LastKeys, Is.EqualTo(new[] { PrimaryKey, SecondaryKey }));
        });
    }

    [Test]
    public async Task PartialUsagePreservesEveryAdapterAndIndexesOnlyTheUnsupportedOne()
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters =
            [
                Adapter(PrimaryKey, "Same model", 16 * Gibibyte, 0, 32 * Gibibyte),
                Adapter(SecondaryKey, "Same model", 8 * Gibibyte, 0, 16 * Gibibyte),
            ],
            Usage =
            [
                new GpuUsageReading(
                    SecondaryKey,
                    7.5,
                    2 * Gibibyte,
                    512 * 1024 * 1024),
            ],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(2));
            Assert.That(snapshot.Adapters.Select(static adapter => adapter.Name),
                Is.EqualTo(new[] { "Same model", "Same model" }));
            Assert.That(snapshot.Adapters[0].UsagePercent, Is.Null);
            Assert.That(snapshot.Adapters[0].DedicatedMemoryUsageBytes, Is.Null);
            Assert.That(snapshot.Adapters[0].SharedMemoryUsageBytes, Is.Null);
            Assert.That(snapshot.Adapters[1].UsagePercent, Is.EqualTo(7.5));
            Assert.That(snapshot.Adapters[1].DedicatedMemoryUsageBytes,
                Is.EqualTo(2 * Gibibyte));
            Assert.That(snapshot.Adapters[1].SharedMemoryUsageBytes,
                Is.EqualTo(512 * 1024 * 1024));
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new GpuStatusFailure(
                        GpuStatusScope.Usage,
                        SystemStatusErrorCodes.Unsupported,
                        AdapterIndex: 0),
                }));
        });
    }

    [Test]
    public async Task EmptyUsageUsesOneGlobalUnsupportedFailureWithoutDroppingAdapters()
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters =
            [
                Adapter(PrimaryKey, "Primary", 16 * Gibibyte, 0, 32 * Gibibyte),
                Adapter(SecondaryKey, "Secondary", 8 * Gibibyte, 0, 16 * Gibibyte),
            ],
            Usage = [],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(2));
            Assert.That(snapshot.Adapters, Has.All.Matches<GpuAdapterStatus>(adapter =>
                adapter.UsagePercent is null
                && adapter.DedicatedMemoryUsageBytes is null
                && adapter.SharedMemoryUsageBytes is null));
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new GpuStatusFailure(
                        GpuStatusScope.Usage,
                        SystemStatusErrorCodes.Unsupported),
                }));
            Assert.That(snapshot.Failures[0].AdapterIndex, Is.Null);
        });
    }

    [TestCase("bad\0name")]
    [TestCase("GPU\u202Eexe")]
    [TestCase("")]
    public async Task InvalidIdentityFailsClosedWithoutSamplingUsage(string name)
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [Adapter(PrimaryKey, name, 16 * Gibibyte, 0, 32 * Gibibyte)],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.That(snapshot.Adapters, Is.Empty);
        Assert.That(
            snapshot.Failures,
            Is.EqualTo(new[]
            {
                new GpuStatusFailure(
                    GpuStatusScope.Identity,
                    SystemStatusErrorCodes.InvalidMeasurement),
            }));
        Assert.That(probe.UsageCalls, Is.Zero);
    }

    [Test]
    public async Task NullIdentityReadingFailsClosedWithoutDereferencingIt()
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [null!],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Identity,
            CancellationToken.None);

        Assert.That(snapshot.Adapters, Is.Empty);
        Assert.That(
            snapshot.Failures,
            Is.EqualTo(new[]
            {
                new GpuStatusFailure(
                    GpuStatusScope.Identity,
                    SystemStatusErrorCodes.InvalidMeasurement),
            }));
    }

    [Test]
    public async Task OverflowingDedicatedCapacityInvalidatesIdentityBeforePublication()
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [Adapter(PrimaryKey, "Example", ulong.MaxValue, 1, 16 * Gibibyte)],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Identity,
            CancellationToken.None);

        Assert.That(snapshot.Adapters, Is.Empty);
        Assert.That(
            snapshot.Failures,
            Is.EqualTo(new[]
            {
                new GpuStatusFailure(
                    GpuStatusScope.Identity,
                    SystemStatusErrorCodes.InvalidMeasurement),
            }));
    }

    [Test]
    public async Task UsageFailurePreservesIdentityAndSanitizesPrivateExceptionDetails()
    {
        const string sensitive = @"user@example.invalid C:\Users\Private 192.0.2.44";
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [Adapter(PrimaryKey, "Example", 8 * Gibibyte, 0, 16 * Gibibyte)],
            UsageException = new IOException(sensitive),
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(1));
            Assert.That(snapshot.Adapters[0].UsagePercent, Is.Null);
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new GpuStatusFailure(
                        GpuStatusScope.Usage,
                        SystemStatusErrorCodes.MeasurementFailed),
                }));
            Assert.That(snapshot.ToString(), Does.Not.Contain("Private"));
            Assert.That(snapshot.ToString(), Does.Not.Contain("192.0.2.44"));
        });
    }

    [Test]
    public async Task InvalidProbeMeasurementUsesExactSanitizedClassification()
    {
        const string sensitive = @"pid_123_luid_0xDEADBEEF C:\Users\Private";
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [Adapter(PrimaryKey, "Example", 8 * Gibibyte, 0, 16 * Gibibyte)],
            UsageException = new GpuInvalidMeasurementException(sensitive),
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(1));
            Assert.That(snapshot.Adapters[0].UsagePercent, Is.Null);
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new GpuStatusFailure(
                        GpuStatusScope.Usage,
                        SystemStatusErrorCodes.InvalidMeasurement),
                }));
            Assert.That(snapshot.ToString(), Does.Not.Contain("DEADBEEF"));
            Assert.That(snapshot.ToString(), Does.Not.Contain("Private"));
        });
    }

    [TestCase(typeof(DllNotFoundException))]
    [TestCase(typeof(EntryPointNotFoundException))]
    public async Task MissingNativeApiIsReportedAsSanitizedUnsupported(Type exceptionType)
    {
        const string sensitive = @"C:\Users\Private\native.dll";
        var probe = new FakeGpuStatusProbe
        {
            AdapterException = (Exception)Activator.CreateInstance(exceptionType, sensitive)!,
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Identity,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Adapters, Is.Empty);
            Assert.That(
                snapshot.Failures,
                Is.EqualTo(new[]
                {
                    new GpuStatusFailure(
                        GpuStatusScope.Identity,
                        SystemStatusErrorCodes.Unsupported),
                }));
            Assert.That(snapshot.ToString(), Does.Not.Contain("Private"));
            Assert.That(snapshot.ToString(), Does.Not.Contain("native.dll"));
        });
    }

    [TestCase(double.NaN)]
    [TestCase(-0.1)]
    [TestCase(100.1)]
    public async Task InvalidUsageDoesNotPublishAnyPartialUsage(double percentage)
    {
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [Adapter(PrimaryKey, "Example", 8 * Gibibyte, 0, 16 * Gibibyte)],
            Usage = [new GpuUsageReading(PrimaryKey, percentage, 1, 2)],
        };
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(1));
            Assert.That(snapshot.Adapters[0].UsagePercent, Is.Null);
            Assert.That(snapshot.Adapters[0].DedicatedMemoryUsageBytes, Is.Null);
            Assert.That(snapshot.Adapters[0].SharedMemoryUsageBytes, Is.Null);
            Assert.That(
                snapshot.Failures.Single(),
                Is.EqualTo(new GpuStatusFailure(
                    GpuStatusScope.Usage,
                    SystemStatusErrorCodes.InvalidMeasurement)));
        });
    }

    [Test]
    public void CancellationBeforeCollectionDoesNotTouchWindows()
    {
        var probe = new FakeGpuStatusProbe();
        var provider = CreateProvider(probe);
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();

        Assert.That(
            async () => await provider.GetStatusAsync(
                GpuStatusScope.Identity,
                cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(probe.AdapterCalls, Is.Zero);
    }

    [Test]
    public async Task CancellationDuringUsageSamplingPropagatesWithoutPublishingSnapshot()
    {
        var entered = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var probe = new FakeGpuStatusProbe
        {
            Adapters = [Adapter(PrimaryKey, "Example", 8 * Gibibyte, 0, 16 * Gibibyte)],
            ReadUsage = async (_, _, cancellationToken) =>
            {
                entered.TrySetResult();
                await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
                return Array.Empty<GpuUsageReading>();
            },
        };
        var provider = CreateProvider(probe);
        using var cancellation = new CancellationTokenSource();

        Task<GpuStatusSnapshot> pending = provider.GetStatusAsync(
            GpuStatusScope.Usage,
            cancellation.Token).AsTask();
        await entered.Task;
        cancellation.Cancel();

        Assert.That(async () => await pending, Throws.InstanceOf<OperationCanceledException>());
        Assert.That(probe.UsageCalls, Is.EqualTo(1));
    }

    [Test]
    public void InvalidScopeIsRejectedBeforeCollection()
    {
        var probe = new FakeGpuStatusProbe();
        var provider = CreateProvider(probe);

        Assert.That(
            async () => await provider.GetStatusAsync(
                (GpuStatusScope)99,
                CancellationToken.None),
            Throws.TypeOf<ArgumentOutOfRangeException>());
        Assert.That(probe.AdapterCalls, Is.Zero);
    }

    [Test]
    public void PublicGpuContractContainsNoProcessTemperatureOrLocalIdentifierFields()
    {
        Type[] types =
        [
            typeof(GpuAdapterStatus),
            typeof(GpuStatusFailure),
            typeof(GpuStatusSnapshot),
        ];
        string[] forbidden =
        [
            "AdapterLuid",
            "ProcessId",
            "Processes",
            "Temperature",
            "Power",
            "FanSpeed",
            "ClockSpeed",
        ];

        string[] properties = types
            .SelectMany(static type => type.GetProperties(BindingFlags.Instance | BindingFlags.Public))
            .Select(static property => property.Name)
            .ToArray();

        Assert.That(properties, Has.None.Matches<string>(forbidden.Contains));
    }

    [Test]
    public async Task AdapterHotPlugRetriesWholeSnapshotOnceWithANewSession()
    {
        var probe = new FakeGpuStatusProbe();
        probe.IsCurrentResults.Enqueue(false);
        probe.IsCurrentResults.Enqueue(true);
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Usage,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Failures, Is.Empty);
            Assert.That(snapshot.Adapters, Has.Count.EqualTo(1));
            Assert.That(probe.SessionCalls, Is.EqualTo(2));
            Assert.That(probe.AdapterCalls, Is.EqualTo(2));
            Assert.That(probe.UsageCalls, Is.EqualTo(2));
            Assert.That(probe.DisposeCalls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task RepeatedAdapterHotPlugFailsWithoutPublishingStaleIdentity()
    {
        var probe = new FakeGpuStatusProbe();
        probe.IsCurrentResults.Enqueue(false);
        probe.IsCurrentResults.Enqueue(false);
        var provider = CreateProvider(probe);

        GpuStatusSnapshot snapshot = await provider.GetStatusAsync(
            GpuStatusScope.Identity,
            CancellationToken.None);

        Assert.That(snapshot.Adapters, Is.Empty);
        Assert.That(
            snapshot.Failures.Single(),
            Is.EqualTo(new GpuStatusFailure(
                GpuStatusScope.Identity,
                SystemStatusErrorCodes.MeasurementFailed)));
        Assert.That(probe.SessionCalls, Is.EqualTo(2));
    }

    private static WindowsGpuStatusProvider CreateProvider(FakeGpuStatusProbe probe) =>
        new(probe, TimeSpan.FromMilliseconds(10));

    private static GpuAdapterReading Adapter(
        GpuAdapterKey key,
        string name,
        ulong dedicatedVideo,
        ulong dedicatedSystem,
        ulong shared) => new(
            key,
            name,
            0x10DE,
            0x2803,
            dedicatedVideo,
            dedicatedSystem,
            shared);

    private sealed class FakeGpuStatusProbe : IGpuStatusProbe
    {
        public IReadOnlyList<GpuAdapterReading> Adapters { get; set; } =
            [Adapter(PrimaryKey, "Example", 8 * Gibibyte, 0, 16 * Gibibyte)];

        public IReadOnlyList<GpuUsageReading> Usage { get; set; } =
            [new GpuUsageReading(PrimaryKey, 25, Gibibyte, 128 * 1024 * 1024)];

        public Exception? AdapterException { get; set; }

        public Exception? UsageException { get; set; }

        public Func<
            IReadOnlyList<GpuAdapterKey>,
            TimeSpan,
            CancellationToken,
            ValueTask<IReadOnlyList<GpuUsageReading>>>
            ? ReadUsage
        { get; set; }

        public Queue<bool> IsCurrentResults { get; } = new();

        public int SessionCalls { get; private set; }

        public int AdapterCalls { get; private set; }

        public int UsageCalls { get; private set; }

        public int DisposeCalls { get; private set; }

        public IReadOnlyList<GpuAdapterKey>? LastKeys { get; private set; }

        public TimeSpan LastSamplingInterval { get; private set; }

        public IGpuStatusProbeSession OpenSession()
        {
            SessionCalls++;
            return new Session(this);
        }

        private sealed class Session(FakeGpuStatusProbe owner) : IGpuStatusProbeSession
        {
            public IReadOnlyList<GpuAdapterReading> ReadAdapters()
            {
                owner.AdapterCalls++;
                if (owner.AdapterException is not null)
                {
                    throw owner.AdapterException;
                }

                return owner.Adapters;
            }

            public ValueTask<IReadOnlyList<GpuUsageReading>> ReadUsageAsync(
                IReadOnlyList<GpuAdapterKey> adapters,
                TimeSpan samplingInterval,
                CancellationToken cancellationToken)
            {
                owner.UsageCalls++;
                owner.LastKeys = adapters;
                owner.LastSamplingInterval = samplingInterval;
                if (owner.UsageException is not null)
                {
                    throw owner.UsageException;
                }

                return owner.ReadUsage is null
                    ? new ValueTask<IReadOnlyList<GpuUsageReading>>(owner.Usage)
                    : owner.ReadUsage(adapters, samplingInterval, cancellationToken);
            }

            public bool IsCurrent() => owner.IsCurrentResults.Count == 0
                || owner.IsCurrentResults.Dequeue();

            public void Dispose()
            {
                owner.DisposeCalls++;
            }
        }
    }
}
