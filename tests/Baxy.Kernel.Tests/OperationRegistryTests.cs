using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class OperationRegistryTests
{
    [Test]
    public void Registry_orders_canonical_names_and_resolves_exactly()
    {
        var zeta = new StubHandler("note.read");
        var alpha = new StubHandler("app.status");
        var registry = new OperationRegistry([zeta, alpha]);

        Assert.That(registry.Definitions.Select(static item => item.Name),
            Is.EqualTo(new[] { "app.status", "note.read" }));
        Assert.That(registry.TryGet("note.read", out IOperationHandler? resolved), Is.True);
        Assert.That(resolved, Is.SameAs(zeta));
        Assert.That(registry.TryGet("NOTE.READ", out _), Is.False);
    }

    [Test]
    public void Registry_rejects_duplicates_and_noncanonical_names()
    {
        Assert.That(
            () => new OperationRegistry([new StubHandler("note.read"), new StubHandler("note.read")]),
            Throws.ArgumentException);
        Assert.That(
            () => new OperationRegistry([new StubHandler("terminal_run")]),
            Throws.ArgumentException);
    }

    [TestCase(OperationRisk.ReadOnly, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Reversible, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Sensitive, PolicyDecision.RequireConfirmation)]
    [TestCase(OperationRisk.External, PolicyDecision.RequireConfirmation)]
    [TestCase(OperationRisk.Irreversible, PolicyDecision.RequireConfirmation)]
    [TestCase(OperationRisk.Forbidden, PolicyDecision.Deny)]
    public void Policy_is_proportional_and_fail_closed(
        OperationRisk risk,
        PolicyDecision expected)
    {
        Assert.That(RiskPolicy.Evaluate(risk), Is.EqualTo(expected));
    }

    private sealed class StubHandler(string name) : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new(name, OperationRisk.ReadOnly, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(OperationOutcome.Success(JsonDocument.Parse("{}").RootElement.Clone()));
        }
    }
}
