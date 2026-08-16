using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class SystemStatusHandlerTests
{
    [Test]
    public void DefinitionIsReadOnly()
    {
        var handler = Handler(new StubProvider(Complete(SystemStatusScope.All)));

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo("system.status"));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.ReadOnly));
        });
    }

    [TestCase("{}", "summary", SystemStatusScope.All)]
    [TestCase("{\"scope\":\"summary\"}", "summary", SystemStatusScope.All)]
    [TestCase("{\"scope\":\"cpu_memory\"}", "cpu_memory", SystemStatusScope.Cpu | SystemStatusScope.Memory)]
    [TestCase("{\"scope\":\"os_memory\"}", "os_memory", SystemStatusScope.OperatingSystem | SystemStatusScope.Memory)]
    [TestCase("{\"scope\":\"cpu\"}", "cpu", SystemStatusScope.Cpu)]
    [TestCase("{\"scope\":\"memory\"}", "memory", SystemStatusScope.Memory)]
    [TestCase("{\"scope\":\"disk\"}", "disk", SystemStatusScope.SystemDisk)]
    [TestCase("{\"scope\":\"battery\"}", "battery", SystemStatusScope.Battery)]
    [TestCase("{\"scope\":\"os\"}", "os", SystemStatusScope.OperatingSystem)]
    public async Task ExactScopeSelectsOnlyTheRequestedMeasurements(
        string json,
        string expectedPublicScope,
        SystemStatusScope expectedProviderScope)
    {
        var provider = new StubProvider(scope => Complete(scope));
        var handler = Handler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result?.GetProperty("scope").GetString(), Is.EqualTo(expectedPublicScope));
            Assert.That(provider.LastScope, Is.EqualTo(expectedProviderScope));
            Assert.That(provider.CallCount, Is.EqualTo(1));
        });
    }

    [TestCase("null")]
    [TestCase("[]")]
    [TestCase("{\"scope\":null}")]
    [TestCase("{\"scope\":42}")]
    [TestCase("{\"scope\":\"CPU\"}")]
    [TestCase("{\"scope\":\" cpu \"}")]
    [TestCase("{\"scope\":\"uptime\"}")]
    [TestCase("{\"scope\":\"summary\",\"extra\":true}")]
    [TestCase("{\"Scope\":\"cpu\"}")]
    [TestCase("{\"scope\":\"cpu\",\"scope\":\"memory\"}")]
    public async Task InvalidArgumentsNeverReachProvider(string json)
    {
        var provider = new StubProvider(Complete(SystemStatusScope.All));
        var handler = Handler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
            Assert.That(provider.CallCount, Is.Zero);
        });
    }

    [Test]
    public async Task SummaryReturnsStructuredVerifiedMeasurementsAndNaturalText()
    {
        var handler = Handler(new StubProvider(Complete(SystemStatusScope.All)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{}"),
            CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("cpu").GetProperty("usagePercent").GetDouble(), Is.EqualTo(17.5d));
            Assert.That(result.GetProperty("cpu").GetProperty("model").GetString(), Is.EqualTo("CPU de prueba"));
            Assert.That(result.GetProperty("memory").GetProperty("totalBytes").GetUInt64(), Is.EqualTo(32UL * GiB));
            Assert.That(result.GetProperty("disk").GetProperty("availableBytes").GetInt64(), Is.EqualTo(200L * GiB));
            Assert.That(result.GetProperty("battery").GetProperty("isPresent").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("os").GetProperty("buildNumber").GetInt32(), Is.EqualTo(26100));
            Assert.That(result.GetProperty("os").GetProperty("isWorkstation").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("uptimeSeconds").GetInt64(), Is.EqualTo(5400));
            Assert.That(result.GetProperty("failures").GetArrayLength(), Is.Zero);
            Assert.That(Message(outcome), Does.Contain("CPU de prueba"));
            Assert.That(Message(outcome), Does.Contain("RAM"));
            Assert.That(Message(outcome), Does.Contain("Windows 11 (versión interna 10.0)"));
            Assert.That(Message(outcome).TrimStart(), Does.Not.StartWith("{"));
        });
    }

    [Test]
    public async Task ServerProductTypeIsNotMisreportedAsWindowsEleven()
    {
        SystemStatusSnapshot snapshot = Complete(SystemStatusScope.OperatingSystem) with
        {
            OperatingSystem = new OperatingSystemStatus(10, 0, 26100, "x64", false),
        };
        var handler = Handler(new StubProvider(snapshot));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"os\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(Message(outcome), Does.StartWith("Windows Server (versión interna 10.0)"));
            Assert.That(Message(outcome), Does.Not.Contain("Windows 11"));
        });
    }

    [Test]
    public async Task MissingBatteryIsARealMeasurementRatherThanAFailure()
    {
        SystemStatusSnapshot snapshot = Complete(SystemStatusScope.Battery) with
        {
            Battery = new BatteryStatus(
                IsPresent: false,
                ChargePercent: null,
                IsCharging: null,
                IsAcOnline: true),
        };
        var handler = Handler(new StubProvider(snapshot));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"battery\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result?.GetProperty("battery").GetProperty("isPresent").GetBoolean(), Is.False);
            Assert.That(outcome.Result?.GetProperty("failures").GetArrayLength(), Is.Zero);
            Assert.That(Message(outcome), Does.Contain("no informa una batería instalada"));
            Assert.That(Message(outcome), Does.Contain("conectado a corriente"));
        });
    }

    [Test]
    public async Task UnknownBatteryPresenceDoesNotPretendThatOneWasDetected()
    {
        SystemStatusSnapshot snapshot = Complete(SystemStatusScope.Battery) with
        {
            Battery = new BatteryStatus(
                IsPresent: null,
                ChargePercent: null,
                IsCharging: null,
                IsAcOnline: true),
        };
        var handler = Handler(new StubProvider(snapshot));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"battery\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(Message(outcome), Does.StartWith("Windows no confirmó si hay una batería"));
            Assert.That(Message(outcome), Does.Not.StartWith("Batería:"));
        });
    }

    [Test]
    public async Task PartialSummaryReportsOnlyMeasuredValuesAndNamedFailures()
    {
        SystemStatusSnapshot snapshot = Complete(SystemStatusScope.All) with
        {
            Battery = null,
            Failures =
            [
                new SystemStatusFailure(
                    SystemStatusScope.Battery,
                    SystemStatusErrorCodes.Unsupported),
            ],
        };
        var handler = Handler(new StubProvider(snapshot));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"summary\"}"),
            CancellationToken.None);
        JsonElement result = outcome.Result!.Value;
        JsonElement failure = result.GetProperty("failures")[0];

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(result.GetProperty("battery").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(failure.GetProperty("scope").GetString(), Is.EqualTo("battery"));
            Assert.That(failure.GetProperty("errorCode").GetString(), Is.EqualTo("unsupported"));
            Assert.That(Message(outcome), Does.Contain("No pude medir: batería."));
            Assert.That(Message(outcome), Does.Not.Contain("unsupported"));
        });
    }

    [Test]
    public async Task UnavailableSingleScopeIsATerminalHonestFailureWithEvidence()
    {
        var provider = new StubProvider(Unavailable(
            SystemStatusScope.Battery,
            SystemStatusErrorCodes.Unsupported));
        var handler = Handler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"scope\":\"battery\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("system_status_unavailable"));
            Assert.That(outcome.Result?.GetProperty("scope").GetString(), Is.EqualTo("battery"));
            Assert.That(outcome.Result?.GetProperty("failures")[0].GetProperty("errorCode").GetString(),
                Is.EqualTo("unsupported"));
            Assert.That(Message(outcome), Does.Contain("No pude"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
        });
    }

    [Test]
    public async Task ReadOnlyFailureIsJournaledAndReplayedWithoutASecondMeasurement()
    {
        var provider = new StubProvider(Unavailable(
            SystemStatusScope.Battery,
            SystemStatusErrorCodes.MeasurementFailed));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([Handler(provider)]),
            journal);
        OperationRequest request = Request("{\"scope\":\"battery\"}");

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = NewId() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.ErrorCode, Is.EqualTo("system_status_unavailable"));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.Result?.GetProperty("failures")[0].GetProperty("scope").GetString(),
                Is.EqualTo("battery"));
            Assert.That(provider.CallCount, Is.EqualTo(1));
        });
    }

    [TestCase("missing")]
    [TestCase("value_and_failure")]
    [TestCase("unrequested_value")]
    [TestCase("duplicate_failure")]
    [TestCase("combined_failure_scope")]
    [TestCase("unknown_failure")]
    [TestCase("cpu_percentage")]
    [TestCase("cpu_count")]
    [TestCase("cpu_model")]
    [TestCase("cpu_model_invalid_unicode")]
    [TestCase("battery_absent_percentage")]
    [TestCase("battery_unknown_charging")]
    [TestCase("os_major")]
    [TestCase("uptime")]
    public async Task ContradictoryOrInvalidProviderEvidenceFailsClosed(string defect)
    {
        (string json, SystemStatusSnapshot snapshot) = Contradicted(defect);
        var provider = new StubProvider(snapshot);
        var handler = Handler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.Result, Is.Null);
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
            Assert.That(provider.CallCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void CancellationIsNotConvertedIntoAStatusResponse()
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var handler = Handler(new StubProvider(Complete(SystemStatusScope.All)));

        Assert.That(
            async () => await handler.ExecuteAsync(Invocation("{}"), cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());
    }

    private const ulong GiB = 1024UL * 1024UL * 1024UL;

    private static SystemStatusSnapshot Complete(SystemStatusScope scope) => new(
        scope.HasFlag(SystemStatusScope.Cpu)
            ? new CpuStatus(17.5d, 24, "CPU de prueba")
            : null,
        scope.HasFlag(SystemStatusScope.Memory)
            ? new MemoryStatus(32UL * GiB, 12UL * GiB)
            : null,
        scope.HasFlag(SystemStatusScope.SystemDisk)
            ? new SystemDiskStatus(1000L * (long)GiB, 200L * (long)GiB)
            : null,
        scope.HasFlag(SystemStatusScope.Battery)
            ? new BatteryStatus(true, 73, false, false)
            : null,
        scope.HasFlag(SystemStatusScope.OperatingSystem)
            ? new OperatingSystemStatus(10, 0, 26100, "x64", true)
            : null,
        scope.HasFlag(SystemStatusScope.Uptime) ? 5400 : null,
        []);

    private static SystemStatusSnapshot Unavailable(
        SystemStatusScope scope,
        string errorCode) => new(
            Cpu: null,
            Memory: null,
            SystemDisk: null,
            Battery: null,
            OperatingSystem: null,
            UptimeSeconds: null,
            [new SystemStatusFailure(scope, errorCode)]);

    private static (string Json, SystemStatusSnapshot Snapshot) Contradicted(string defect)
    {
        const string cpuJson = "{\"scope\":\"cpu\"}";
        return defect switch
        {
            "missing" => (cpuJson, Complete(SystemStatusScope.Cpu) with { Cpu = null }),
            "value_and_failure" => (cpuJson, Complete(SystemStatusScope.Cpu) with
            {
                Failures =
                [
                    new SystemStatusFailure(
                        SystemStatusScope.Cpu,
                        SystemStatusErrorCodes.MeasurementFailed),
                ],
            }),
            "unrequested_value" => (cpuJson, Complete(SystemStatusScope.Cpu) with
            {
                Memory = new MemoryStatus(32UL * GiB, 12UL * GiB),
            }),
            "duplicate_failure" => (cpuJson, Unavailable(
                SystemStatusScope.Cpu,
                SystemStatusErrorCodes.MeasurementFailed) with
            {
                Failures =
                [
                    new SystemStatusFailure(
                        SystemStatusScope.Cpu,
                        SystemStatusErrorCodes.MeasurementFailed),
                    new SystemStatusFailure(
                        SystemStatusScope.Cpu,
                        SystemStatusErrorCodes.Unsupported),
                ],
            }),
            "combined_failure_scope" => (cpuJson, Unavailable(
                SystemStatusScope.Cpu | SystemStatusScope.Memory,
                SystemStatusErrorCodes.MeasurementFailed)),
            "unknown_failure" => (cpuJson, Unavailable(SystemStatusScope.Cpu, "unknown")),
            "cpu_percentage" => (cpuJson, Complete(SystemStatusScope.Cpu) with
            {
                Cpu = new CpuStatus(double.NaN, 24, null),
            }),
            "cpu_count" => (cpuJson, Complete(SystemStatusScope.Cpu) with
            {
                Cpu = new CpuStatus(17.5d, 0, null),
            }),
            "cpu_model" => (cpuJson, Complete(SystemStatusScope.Cpu) with
            {
                Cpu = new CpuStatus(17.5d, 24, "e\u0301"),
            }),
            "cpu_model_invalid_unicode" => (cpuJson, Complete(SystemStatusScope.Cpu) with
            {
                Cpu = new CpuStatus(17.5d, 24, "\ud800"),
            }),
            "battery_absent_percentage" => ("{\"scope\":\"battery\"}",
                Complete(SystemStatusScope.Battery) with
                {
                    Battery = new BatteryStatus(false, 73, null, true),
                }),
            "battery_unknown_charging" => ("{\"scope\":\"battery\"}",
                Complete(SystemStatusScope.Battery) with
                {
                    Battery = new BatteryStatus(null, null, false, true),
                }),
            "os_major" => ("{\"scope\":\"os\"}", Complete(SystemStatusScope.OperatingSystem) with
            {
                OperatingSystem = new OperatingSystemStatus(0, 0, 26100, "x64", true),
            }),
            "uptime" => ("{}", Complete(SystemStatusScope.All) with { UptimeSeconds = -1 }),
            _ => throw new AssertionException($"Unknown contradiction: {defect}"),
        };
    }

    private static OperationInvocation Invocation(string json) => new(
        NewId(),
        NewId(),
        NewId(),
        Parse(json));

    private static OperationRequest Request(string json) => new(
        ProtocolTypes.OperationRequest,
        NewId(),
        NewId(),
        NewId(),
        "system.status",
        Parse(json));

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static SystemStatusHandler Handler(ISystemStatusProvider provider) => new(
        provider,
        new StubGpuProvider(new GpuStatusSnapshot(
            [new GpuAdapterStatus("GPU de prueba", 1, 1, GiB, 0, 2 * GiB, null, null, null)],
            [])));

    private static string Message(OperationOutcome outcome) =>
        OperationOutcomeNarration.For("system.status", outcome);

    private sealed class StubGpuProvider(GpuStatusSnapshot result) : IGpuStatusProvider
    {
        public ValueTask<GpuStatusSnapshot> GetStatusAsync(
            GpuStatusScope scope,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubProvider : ISystemStatusProvider
    {
        private readonly Func<SystemStatusScope, SystemStatusSnapshot> _result;

        public StubProvider(SystemStatusSnapshot result)
            : this(_ => result)
        {
        }

        public StubProvider(Func<SystemStatusScope, SystemStatusSnapshot> result)
        {
            _result = result;
        }

        public int CallCount { get; private set; }

        public SystemStatusScope? LastScope { get; private set; }

        public ValueTask<SystemStatusSnapshot> GetStatusAsync(
            SystemStatusScope scope,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CallCount++;
            LastScope = scope;
            return ValueTask.FromResult(_result(scope));
        }
    }
}
