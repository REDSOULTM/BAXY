using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ProcessListHandlerTests
{
    [Test]
    public async Task DefaultRequestReturnsOnlyBoundedVerifiedProcessFields()
    {
        var provider = new StubProvider(new ProcessStatusSnapshot(
            42,
            [
                new ProcessStatusEntry(101, 10_000, "alpha", 2_048, 12.5),
                new ProcessStatusEntry(202, 20_000, "beta", 1_024, 3.25),
            ]));
        var handler = new ProcessListHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo("system.process.list"));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.ReadOnly));
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result?.GetProperty("version").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result?.GetProperty("sort").GetString(), Is.EqualTo("memory"));
            Assert.That(outcome.Result?.GetProperty("observedProcessCount").GetInt32(), Is.EqualTo(42));
            Assert.That(outcome.Result?.GetProperty("processes").GetArrayLength(), Is.EqualTo(2));
            Assert.That(outcome.Result?.GetProperty("returnedProcessCount").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result?.GetProperty("observationScope").GetString(), Is.EqualTo("accessible_processes"));
            Assert.That(provider.LastSort, Is.EqualTo(ProcessStatusSort.Memory));
            Assert.That(provider.LastLimit, Is.EqualTo(10));
            Assert.That(
                OperationOutcomeNarration.For("system.process.list", outcome),
                Does.Contain("alpha"));
            Assert.That(
                OperationOutcomeNarration.Facts("system.process.list", outcome)["polarity"]
                    ?.GetValue<string>(),
                Is.EqualTo("success"));
        });
    }

    [Test]
    public async Task CurrentCpuFactsKeepPercentIntervalAndMachineDenominator()
    {
        var handler = new ProcessListHandler(new StubProvider(new ProcessStatusSnapshot(
            42, [new ProcessStatusEntry(101, 10_000, "busy", 2048, 200, 25, 0.2)], 8)));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("{\"sort\":\"cpu\"}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result?.GetProperty("logicalProcessorCount").GetInt32(), Is.EqualTo(8));
            Assert.That(outcome.Result?.GetProperty("processes")[0].GetProperty("cpuUsagePercent").GetDouble(), Is.EqualTo(25));
            Assert.That(outcome.Result?.GetProperty("processes")[0].GetProperty("sampleDurationSeconds").GetDouble(), Is.EqualTo(0.2));
        });
    }

    [Test]
    public async Task FullProcessPageKeepsEveryInstanceThroughVisibleFacts()
    {
        var rows = Enumerable.Range(1, 50).Select(index =>
            new ProcessStatusEntry(index, 1000 + index, new string('a', 400), 2048, index, 0.5, 0.2)).ToArray();
        var handler = new ProcessListHandler(new StubProvider(new ProcessStatusSnapshot(207, rows, 8)));
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"sort\":\"cpu\",\"limit\":50}"), CancellationToken.None);

        string rawFacts = OperationVisibleFacts.FromOutcome("system.process.list", outcome);
        var response = new OperationResponse(ProtocolTypes.OperationResponse, "request", "mission", "invocation",
            OperationStatuses.Completed, rawFacts, true, false, outcome.Result, null);
        string projected = OperationResponseProjection.Create(response, "system.process.list").Message;
        JsonNode facts = JsonNode.Parse(projected)!;
        JsonArray visibleRows = facts["observed"]!["processes"]!.AsArray();

        Assert.Multiple(() =>
        {
            Assert.That(rawFacts.Length, Is.GreaterThan(16_384));
            Assert.That(projected, Is.EqualTo(rawFacts));
            Assert.That(visibleRows.Count, Is.EqualTo(50));
            Assert.That(visibleRows.Select(row => row!["processId"]!.GetValue<int>()), Is.EqualTo(Enumerable.Range(1, 50)));
            Assert.That(facts["observed"]!["observedProcessCount"]!.GetValue<int>(), Is.EqualTo(207));
            Assert.That(facts["observed"]!["returnedProcessCount"]!.GetValue<int>(), Is.EqualTo(50));
        });
    }

    [TestCase("system.process.list", true)]
    [TestCase("app.open", false)]
    public void ProcessIdsAreVisibleOnlyForTheRequestedInventory(string operation, bool visible)
    {
        using var result = JsonDocument.Parse("""{"processId":731,"token":"secret","handle":99,"name":"Editor"}""");
        JsonNode facts = JsonNode.Parse(OperationVisibleFacts.FromOutcome(operation,
            OperationOutcome.Success(result.RootElement.Clone())))!;
        JsonObject observed = facts["observed"]!.AsObject();

        Assert.Multiple(() =>
        {
            Assert.That(observed.ContainsKey("processId"), Is.EqualTo(visible));
            Assert.That(observed.ContainsKey("token"), Is.False);
            Assert.That(observed.ContainsKey("handle"), Is.False);
            Assert.That(observed["name"]!.GetValue<string>(), Is.EqualTo("Editor"));
        });
    }

    [TestCase(null, 0.2, 8)]
    [TestCase(101.0, 0.2, 8)]
    [TestCase(-1.0, 0.2, 8)]
    [TestCase(double.NaN, 0.2, 8)]
    [TestCase(25.0, null, 8)]
    [TestCase(25.0, 0.0, 8)]
    [TestCase(25.0, double.PositiveInfinity, 8)]
    [TestCase(25.0, 0.2, null)]
    public async Task LifetimeCpuAloneAndInvalidMeasurementsCannotClaimCurrentCpu(
        double? percent, double? duration, int? logicalCount)
    {
        var handler = new ProcessListHandler(new StubProvider(new ProcessStatusSnapshot(
            42, [new ProcessStatusEntry(101, 10_000, "busy", 2048, 200, percent, duration)], logicalCount)));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("{\"sort\":\"cpu\"}"), CancellationToken.None);

        Assert.That(outcome.ErrorCode, Is.EqualTo("process_inventory_unavailable"));
    }

    [TestCase("null")]
    [TestCase("[]")]
    [TestCase("{\"sort\":\"CPU\"}")]
    [TestCase("{\"limit\":0}")]
    [TestCase("{\"limit\":51}")]
    [TestCase("{\"extra\":true}")]
    [TestCase("{\"sort\":\"cpu\",\"sort\":\"memory\"}")]
    public async Task InvalidArgumentsNeverReachProvider(string json)
    {
        var provider = new StubProvider(new ProcessStatusSnapshot(1, []));
        var handler = new ProcessListHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(provider.CallCount, Is.Zero);
        });
    }

    [Test]
    public async Task ContradictoryOrUnverifiedInventoryFailsClosed()
    {
        var provider = new StubProvider(new ProcessStatusSnapshot(
            1,
            [new ProcessStatusEntry(0, 1, "invalid", 1, 1)]));
        var handler = new ProcessListHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"sort\":\"cpu\",\"limit\":1}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("process_inventory_unavailable"));
            Assert.That(
                OperationOutcomeNarration.For("system.process.list", outcome),
                Does.Not.StartWith("Listo"));
        });
    }

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());

    private sealed class StubProvider(ProcessStatusSnapshot result) : IProcessStatusProvider
    {
        public int CallCount { get; private set; }
        public int LastLimit { get; private set; }
        public ProcessStatusSort? LastSort { get; private set; }

        public ValueTask<ProcessStatusSnapshot> GetProcessesAsync(
            ProcessStatusSort sort,
            int limit,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CallCount++;
            LastSort = sort;
            LastLimit = limit;
            return ValueTask.FromResult(result);
        }
    }
}
