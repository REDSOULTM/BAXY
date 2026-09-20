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

    // D3 (DECISIONES_DUENO_2026-09-20.md): only the destructive or irreparable asks
    // in normal mode; privacy_sensitive/installation and external effects that reach
    // no other person go direct.
    [TestCase(OperationRisk.ReadOnly, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Reversible, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Sensitive, PolicyDecision.Allow)]
    [TestCase(OperationRisk.External, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Irreversible, PolicyDecision.RequireConfirmation)]
    [TestCase(OperationRisk.Forbidden, PolicyDecision.Deny)]
    public void Policy_is_proportional_and_fail_closed(
        OperationRisk risk,
        PolicyDecision expected)
    {
        Assert.That(RiskPolicy.Evaluate(risk), Is.EqualTo(expected));
    }

    // D3: what reaches another person keeps asking; playing, navigating, clicking,
    // copying, capturing, typing, radios, settings and installing do not.
    [TestCase("message.send", PolicyDecision.RequireConfirmation)]
    [TestCase("message.send.test", PolicyDecision.RequireConfirmation)]
    [TestCase("email.latest.reply", PolicyDecision.RequireConfirmation)]
    [TestCase("media.play.query", PolicyDecision.Allow)]
    [TestCase("streaming.play.named", PolicyDecision.Allow)]
    [TestCase("browser.navigate.named", PolicyDecision.Allow)]
    [TestCase("input.visible.click", PolicyDecision.Allow)]
    [TestCase("calendar.event.create", PolicyDecision.Allow)]
    [TestCase("capture.screenshot", PolicyDecision.Allow)]
    [TestCase("clipboard.read.text", PolicyDecision.Allow)]
    [TestCase("input.text.type", PolicyDecision.Allow)]
    [TestCase("wifi.radio.set", PolicyDecision.Allow)]
    [TestCase("bluetooth.device.pair", PolicyDecision.Allow)]
    [TestCase("system.settings.set", PolicyDecision.Allow)]
    [TestCase("memory.enable", PolicyDecision.Allow)]
    [TestCase("game.install.named", PolicyDecision.Allow)]
    [TestCase("package.install.commit", PolicyDecision.Allow)]
    [TestCase("game.install.cancel", PolicyDecision.RequireConfirmation)]
    [TestCase("game.purchase.commit", PolicyDecision.RequireConfirmation)]
    [TestCase("memory.forget", PolicyDecision.RequireConfirmation)]
    [TestCase("system.process.terminate.named", PolicyDecision.RequireConfirmation)]
    [TestCase("system.recyclebin.empty", PolicyDecision.RequireConfirmation)]
    [TestCase("window.close.all", PolicyDecision.RequireConfirmation)]
    [TestCase("app.close", PolicyDecision.RequireConfirmation)]
    [TestCase("system.power", PolicyDecision.Allow)]
    public void Normal_mode_asks_only_for_the_destructive_or_what_reaches_another_person(
        string operation,
        PolicyDecision expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(operation);
        Assert.That(
            RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal, operation),
            Is.EqualTo(expected));
        Assert.That(
            RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Bypass, operation),
            Is.EqualTo(PolicyDecision.Allow));
    }

    [TestCase(OperationRisk.Irreversible, ConfirmationMode.Bypass, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Sensitive, ConfirmationMode.Bypass, PolicyDecision.Allow)]
    [TestCase(OperationRisk.External, ConfirmationMode.Bypass, PolicyDecision.Allow)]
    [TestCase(OperationRisk.Forbidden, ConfirmationMode.Bypass, PolicyDecision.Deny)]
    [TestCase(OperationRisk.Reversible, ConfirmationMode.Normal, PolicyDecision.Allow)]
    public void Confirmation_mode_is_one_setting_on_the_same_path(
        OperationRisk risk,
        ConfirmationMode mode,
        PolicyDecision expected)
    {
        Assert.That(RiskPolicy.Evaluate(risk, mode), Is.EqualTo(expected));
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
