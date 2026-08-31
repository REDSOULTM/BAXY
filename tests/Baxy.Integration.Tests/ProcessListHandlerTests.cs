using System.Text.Json;
using System.Text.Json.Nodes;
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
            Assert.That(outcome.Result?.GetProperty("version").GetInt32(), Is.EqualTo(1));
            Assert.That(outcome.Result?.GetProperty("sort").GetString(), Is.EqualTo("memory"));
            Assert.That(outcome.Result?.GetProperty("observedProcessCount").GetInt32(), Is.EqualTo(42));
            Assert.That(outcome.Result?.GetProperty("processes").GetArrayLength(), Is.EqualTo(2));
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
