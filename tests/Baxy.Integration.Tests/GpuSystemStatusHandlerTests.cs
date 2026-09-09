using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class GpuSystemStatusHandlerTests
{
    private const ulong MiB = 1024UL * 1024UL;
    private const ulong GiB = 1024UL * MiB;

    [TestCase("gpu_identity", GpuStatusScope.Identity)]
    [TestCase("gpu_usage", GpuStatusScope.Usage)]
    public async Task GpuScopesUseOnlyTheGpuBranch(
        string publicScope,
        GpuStatusScope providerScope)
    {
        var legacy = new StubSystemStatusProvider(CompleteLegacy);
        var gpu = new StubGpuStatusProvider(scope => scope == GpuStatusScope.Identity
            ? IdentitySnapshot()
            : MeasuredUsageSnapshot());
        var handler = new SystemStatusHandler(legacy, gpu);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation($"{{\"scope\":\"{publicScope}\"}}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result?.GetProperty("scope").GetString(), Is.EqualTo(publicScope));
            Assert.That(gpu.LastScope, Is.EqualTo(providerScope));
            Assert.That(gpu.CallCount, Is.EqualTo(1));
            Assert.That(legacy.CallCount, Is.Zero);
        });
    }

    [Test]
    public async Task SummaryDoesNotQueryGpuOrChangeTheLegacyJsonShape()
    {
        var legacy = new StubSystemStatusProvider(CompleteLegacy);
        var gpu = new StubGpuStatusProvider(_ => throw new AssertionException(
            "Summary must not query GPU."));
        var handler = new SystemStatusHandler(legacy, gpu);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"summary\"}"),
            CancellationToken.None);
        string[] properties = outcome.Result!.Value
            .EnumerateObject()
            .Select(static property => property.Name)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(legacy.LastScope, Is.EqualTo(SystemStatusScope.All));
            Assert.That(gpu.CallCount, Is.Zero);
            Assert.That(properties, Is.EqualTo(new[]
            {
                "scope",
                "cpu",
                "memory",
                "disk",
                "battery",
                "os",
                "uptimeSeconds",
                "failures",
            }));
            Assert.That(outcome.Result?.TryGetProperty("adapters", out _), Is.False);
            Assert.That(outcome.Result?.TryGetProperty("gpu", out _), Is.False);
        });
    }

    [Test]
    public async Task IdentitySeparatesVramReservedRamAndSharedRam()
    {
        var gpu = new StubGpuStatusProvider(IdentitySnapshot());
        var handler = Handler(gpu);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"gpu_identity\"}"),
            CancellationToken.None);
        JsonElement adapter = outcome.Result!.Value.GetProperty("adapters")[0];

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(adapter.GetProperty("adapterIndex").GetInt32(), Is.Zero);
            Assert.That(adapter.GetProperty("name").GetString(), Is.EqualTo("GPU de prueba"));
            Assert.That(adapter.GetProperty("vendorId").GetUInt32(), Is.EqualTo(0x10DE));
            Assert.That(adapter.GetProperty("deviceId").GetUInt32(), Is.EqualTo(0x2803));
            Assert.That(
                adapter.GetProperty("dedicatedVideoMemoryBytes").GetUInt64(),
                Is.EqualTo(8 * GiB));
            Assert.That(
                adapter.GetProperty("dedicatedSystemMemoryBytes").GetUInt64(),
                Is.EqualTo(256 * MiB));
            Assert.That(
                adapter.GetProperty("sharedSystemMemoryLimitBytes").GetUInt64(),
                Is.EqualTo(16 * GiB));
            Assert.That(adapter.GetProperty("usagePercent").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(
                adapter.GetProperty("dedicatedMemoryUsageBytes").ValueKind,
                Is.EqualTo(JsonValueKind.Null));
            Assert.That(
                adapter.GetProperty("sharedMemoryUsageBytes").ValueKind,
                Is.EqualTo(JsonValueKind.Null));
            Assert.That(Message(outcome), Does.Contain("GPU de prueba"));
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
            Assert.That(Message(outcome), Does.Not.Contain("nvidia-smi"));
        });
    }

    [Test]
    public async Task PartialUsagePublishesMeasuredAdaptersAndNamesUnmeasuredOnes()
    {
        GpuStatusSnapshot snapshot = new(
            [
                Adapter("RTX duplicada", 8 * GiB, 0, 16 * GiB, 42.25, 2 * GiB, 256 * MiB),
                Adapter("RTX duplicada", 12 * GiB, 128 * MiB, 24 * GiB),
            ],
            [
                new GpuStatusFailure(
                    GpuStatusScope.Usage,
                    SystemStatusErrorCodes.Unsupported,
                    AdapterIndex: 1),
            ]);
        var gpu = new StubGpuStatusProvider(snapshot);
        var handler = Handler(gpu);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"gpu_usage\"}"),
            CancellationToken.None);
        JsonElement result = outcome.Result!.Value;
        JsonElement measured = result.GetProperty("adapters")[0];
        JsonElement unmeasured = result.GetProperty("adapters")[1];
        JsonElement failure = result.GetProperty("failures")[0];

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(measured.GetProperty("adapterIndex").GetInt32(), Is.Zero);
            Assert.That(measured.GetProperty("usagePercent").GetDouble(), Is.EqualTo(42.25));
            Assert.That(unmeasured.GetProperty("adapterIndex").GetInt32(), Is.EqualTo(1));
            Assert.That(
                unmeasured.GetProperty("usagePercent").ValueKind,
                Is.EqualTo(JsonValueKind.Null));
            Assert.That(
                unmeasured.GetProperty("dedicatedMemoryUsageBytes").ValueKind,
                Is.EqualTo(JsonValueKind.Null));
            Assert.That(
                unmeasured.GetProperty("sharedMemoryUsageBytes").ValueKind,
                Is.EqualTo(JsonValueKind.Null));
            Assert.That(failure.GetProperty("scope").GetString(), Is.EqualTo("gpu_usage"));
            Assert.That(failure.GetProperty("adapterIndex").GetInt32(), Is.EqualTo(1));
            Assert.That(failure.GetProperty("errorCode").GetString(), Is.EqualTo("unsupported"));
            Assert.That(Message(outcome), Does.Contain("RTX duplicada"));
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
            Assert.That(Message(outcome), Does.Not.Contain("nvidia-smi"));
        });
    }

    [Test]
    public async Task NoMeasuredUsageIsAnHonestFailureWithNamedEvidence()
    {
        GpuStatusSnapshot snapshot = new(
            [
                Adapter("GPU A", 8 * GiB, 0, 16 * GiB),
                Adapter("GPU B", 0, 128 * MiB, 16 * GiB),
            ],
            [
                new GpuStatusFailure(
                    GpuStatusScope.Usage,
                    SystemStatusErrorCodes.Unsupported),
            ]);
        var handler = Handler(new StubGpuStatusProvider(snapshot));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"gpu_usage\"}"),
            CancellationToken.None);
        JsonElement failure = outcome.Result!.Value.GetProperty("failures")[0];

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("system_status_unavailable"));
            Assert.That(failure.GetProperty("scope").GetString(), Is.EqualTo("gpu_usage"));
            Assert.That(failure.GetProperty("adapterIndex").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(Message(outcome), Does.Contain("GPU A"));
            Assert.That(Message(outcome), Does.Contain("GPU B"));
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
        });
    }

    [Test]
    public async Task IdentityFailureInsideUsageRemainsExplicitAndUnambiguous()
    {
        GpuStatusSnapshot snapshot = new(
            [],
            [
                new GpuStatusFailure(
                    GpuStatusScope.Identity,
                    SystemStatusErrorCodes.MeasurementFailed),
            ]);
        var handler = Handler(new StubGpuStatusProvider(snapshot));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"gpu_usage\"}"),
            CancellationToken.None);
        JsonElement failure = outcome.Result!.Value.GetProperty("failures")[0];

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("system_status_unavailable"));
            Assert.That(failure.GetProperty("scope").GetString(), Is.EqualTo("gpu_identity"));
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
        });
    }

    [TestCase("measured_and_failure")]
    [TestCase("unmeasured_without_failure")]
    [TestCase("wrong_adapter_index")]
    [TestCase("duplicate_adapter_failure")]
    [TestCase("indexed_non_unsupported")]
    [TestCase("global_with_partial")]
    [TestCase("all_unmeasured_indexed")]
    [TestCase("duplicate_global")]
    [TestCase("identity_failure_with_adapters")]
    [TestCase("empty_without_failure")]
    public async Task PresenceAndFailureContradictionsFailClosed(string defect)
    {
        (GpuStatusScope scope, GpuStatusSnapshot snapshot) = ContradictedPresence(defect);
        var gpu = new StubGpuStatusProvider(snapshot);
        var handler = Handler(gpu);
        string publicScope = scope == GpuStatusScope.Identity
            ? "gpu_identity"
            : "gpu_usage";

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation($"{{\"scope\":\"{publicScope}\"}}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.Result, Is.Null);
            Assert.That(gpu.CallCount, Is.EqualTo(1));
        });
    }

    [TestCase("partial_usage_fields")]
    [TestCase("percentage")]
    [TestCase("dedicated_over_capacity")]
    [TestCase("shared_over_limit")]
    [TestCase("identity_capacity_overflow")]
    [TestCase("decomposed_name")]
    [TestCase("overlong_name")]
    [TestCase("format_control_name")]
    [TestCase("invalid_unicode_name")]
    [TestCase("unknown_failure")]
    [TestCase("too_many_adapters")]
    [TestCase("null_adapters")]
    [TestCase("null_failures")]
    public async Task InvalidGpuEvidenceFailsClosed(string defect)
    {
        (GpuStatusScope scope, GpuStatusSnapshot snapshot) = InvalidEvidence(defect);
        var handler = Handler(new StubGpuStatusProvider(snapshot));
        string publicScope = scope == GpuStatusScope.Identity
            ? "gpu_identity"
            : "gpu_usage";

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation($"{{\"scope\":\"{publicScope}\"}}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.Result, Is.Null);
        });
    }

    [Test]
    public void ProvidersAreRequiredDependencies()
    {
        var legacy = new StubSystemStatusProvider(CompleteLegacy);
        var gpu = new StubGpuStatusProvider(IdentitySnapshot());

        Assert.Multiple(() =>
        {
            Assert.That(
                () => new SystemStatusHandler(null!, gpu),
                Throws.TypeOf<ArgumentNullException>());
            Assert.That(
                () => new SystemStatusHandler(legacy, null!),
                Throws.TypeOf<ArgumentNullException>());
        });
    }

    private static (GpuStatusScope Scope, GpuStatusSnapshot Snapshot) ContradictedPresence(
        string defect)
    {
        GpuAdapterStatus measured = Adapter("GPU A", 8 * GiB, 0, 16 * GiB, 25, GiB, MiB);
        GpuAdapterStatus unmeasured = Adapter("GPU B", 8 * GiB, 0, 16 * GiB);
        return defect switch
        {
            "measured_and_failure" => (GpuStatusScope.Usage, new(
                [measured],
                [new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported, 0)])),
            "unmeasured_without_failure" => (GpuStatusScope.Usage, new([unmeasured], [])),
            "wrong_adapter_index" => (GpuStatusScope.Usage, new(
                [measured, unmeasured],
                [new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported, 0)])),
            "duplicate_adapter_failure" => (GpuStatusScope.Usage, new(
                [measured, unmeasured],
                [
                    new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported, 1),
                    new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported, 1),
                ])),
            "indexed_non_unsupported" => (GpuStatusScope.Usage, new(
                [measured, unmeasured],
                [new(GpuStatusScope.Usage, SystemStatusErrorCodes.MeasurementFailed, 1)])),
            "global_with_partial" => (GpuStatusScope.Usage, new(
                [measured, unmeasured],
                [new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported)])),
            "all_unmeasured_indexed" => (GpuStatusScope.Usage, new(
                [unmeasured],
                [new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported, 0)])),
            "duplicate_global" => (GpuStatusScope.Usage, new(
                [unmeasured],
                [
                    new(GpuStatusScope.Usage, SystemStatusErrorCodes.Unsupported),
                    new(GpuStatusScope.Usage, SystemStatusErrorCodes.MeasurementFailed),
                ])),
            "identity_failure_with_adapters" => (GpuStatusScope.Identity, new(
                [unmeasured],
                [new(GpuStatusScope.Identity, SystemStatusErrorCodes.MeasurementFailed)])),
            "empty_without_failure" => (GpuStatusScope.Identity, new([], [])),
            _ => throw new AssertionException($"Unknown presence defect: {defect}"),
        };
    }

    private static (GpuStatusScope Scope, GpuStatusSnapshot Snapshot) InvalidEvidence(
        string defect)
    {
        GpuAdapterStatus measured = Adapter("GPU A", 8 * GiB, 0, 16 * GiB, 25, GiB, MiB);
        return defect switch
        {
            "partial_usage_fields" => (GpuStatusScope.Usage, new(
                [measured with { DedicatedMemoryUsageBytes = null }],
                [])),
            "percentage" => (GpuStatusScope.Usage, new(
                [measured with { UsagePercent = double.NaN }],
                [])),
            "dedicated_over_capacity" => (GpuStatusScope.Usage, new(
                [measured with { DedicatedMemoryUsageBytes = 9 * GiB }],
                [])),
            "shared_over_limit" => (GpuStatusScope.Usage, new(
                [measured with { SharedMemoryUsageBytes = 17 * GiB }],
                [])),
            "identity_capacity_overflow" => (GpuStatusScope.Identity, new(
                [Adapter("GPU A", ulong.MaxValue, 1, 0)],
                [])),
            "decomposed_name" => (GpuStatusScope.Identity, new(
                [Adapter("e\u0301", GiB, 0, GiB)],
                [])),
            "overlong_name" => (GpuStatusScope.Identity, new(
                [Adapter(new string('é', 257), GiB, 0, GiB)],
                [])),
            "format_control_name" => (GpuStatusScope.Identity, new(
                [Adapter("GPU\u202Eexe", GiB, 0, GiB)],
                [])),
            "invalid_unicode_name" => (GpuStatusScope.Identity, new(
                [Adapter("\ud800", GiB, 0, GiB)],
                [])),
            "unknown_failure" => (GpuStatusScope.Identity, new(
                [],
                [new(GpuStatusScope.Identity, "unknown")])),
            "too_many_adapters" => (GpuStatusScope.Identity, new(
                Enumerable.Range(0, 65)
                    .Select(index => Adapter($"GPU {index}", GiB, 0, GiB))
                    .ToArray(),
                [])),
            "null_adapters" => (GpuStatusScope.Identity, new(null!, [])),
            "null_failures" => (GpuStatusScope.Identity, new([], null!)),
            _ => throw new AssertionException($"Unknown evidence defect: {defect}"),
        };
    }

    private static SystemStatusHandler Handler(IGpuStatusProvider gpuProvider) => new(
        new StubSystemStatusProvider(CompleteLegacy),
        gpuProvider);

    private static GpuStatusSnapshot IdentitySnapshot() => new(
        [Adapter("GPU de prueba", 8 * GiB, 256 * MiB, 16 * GiB)],
        []);

    private static GpuStatusSnapshot MeasuredUsageSnapshot() => new(
        [Adapter("GPU de prueba", 8 * GiB, 0, 16 * GiB, 25, GiB, MiB)],
        []);

    private static GpuAdapterStatus Adapter(
        string name,
        ulong dedicatedVideo,
        ulong dedicatedSystem,
        ulong shared,
        double? usagePercent = null,
        ulong? dedicatedUsage = null,
        ulong? sharedUsage = null) => new(
            name,
            0x10DE,
            0x2803,
            dedicatedVideo,
            dedicatedSystem,
            shared,
            usagePercent,
            dedicatedUsage,
            sharedUsage);

    private static SystemStatusSnapshot CompleteLegacy(SystemStatusScope scope) => new(
        scope.HasFlag(SystemStatusScope.Cpu)
            ? new CpuStatus(12.5, 8, "CPU de prueba")
            : null,
        scope.HasFlag(SystemStatusScope.Memory)
            ? new MemoryStatus(16 * GiB, 8 * GiB)
            : null,
        scope.HasFlag(SystemStatusScope.SystemDisk)
            ? new SystemDiskStatus(512 * (long)GiB, 256 * (long)GiB)
            : null,
        scope.HasFlag(SystemStatusScope.Battery)
            ? new BatteryStatus(false, null, null, true)
            : null,
        scope.HasFlag(SystemStatusScope.OperatingSystem)
            ? new OperatingSystemStatus(10, 0, 26100, "x64", true, "Microsoft Windows 11 Pro")
            : null,
        scope.HasFlag(SystemStatusScope.Uptime) ? 60 : null,
        []);

    private static OperationInvocation Invocation(string json) => new(
        NewId(),
        NewId(),
        NewId(),
        JsonDocument.Parse(json).RootElement.Clone());

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static string Message(OperationOutcome outcome) =>
        OperationOutcomeNarration.For("system.status", outcome);

    private static JsonObject Facts(OperationOutcome outcome) =>
        OperationOutcomeNarration.Facts("system.status", outcome);

    private sealed class StubSystemStatusProvider(
        Func<SystemStatusScope, SystemStatusSnapshot> result) : ISystemStatusProvider
    {
        public int CallCount { get; private set; }

        public SystemStatusScope? LastScope { get; private set; }

        public ValueTask<SystemStatusSnapshot> GetStatusAsync(
            SystemStatusScope scope,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CallCount++;
            LastScope = scope;
            return ValueTask.FromResult(result(scope));
        }
    }

    private sealed class StubGpuStatusProvider : IGpuStatusProvider
    {
        private readonly Func<GpuStatusScope, GpuStatusSnapshot> _result;

        public StubGpuStatusProvider(GpuStatusSnapshot result)
            : this(_ => result)
        {
        }

        public StubGpuStatusProvider(Func<GpuStatusScope, GpuStatusSnapshot> result)
        {
            _result = result;
        }

        public int CallCount { get; private set; }

        public GpuStatusScope? LastScope { get; private set; }

        public ValueTask<GpuStatusSnapshot> GetStatusAsync(
            GpuStatusScope scope,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CallCount++;
            LastScope = scope;
            return ValueTask.FromResult(_result(scope));
        }
    }
}
