using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ExternalCapabilityHandlerTests
{
    [Test]
    public async Task ControlledAdapterCanReturnOnlyMatchingVerifiedStructuredEvidence()
    {
        using JsonDocument evidence = JsonDocument.Parse("{\"version\":1,\"messageId\":\"msg_test\"}");
        var provider = new StubProvider(operation => new ExternalCapabilityReceipt(
            operation, true, true, evidence.RootElement.Clone(), null));
        var handler = new ExternalCapabilityHandler("message.send", provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"recipientId\":\"recipient_test\",\"text\":\"hola\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("messageId").GetString(), Is.EqualTo("msg_test"));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.External));
        });
    }

    [Test]
    public async Task UnverifiedOrMismatchedAdapterEvidenceFailsClosed()
    {
        using JsonDocument evidence = JsonDocument.Parse("{\"version\":1}");
        var handler = new ExternalCapabilityHandler(
            "game.purchase.commit",
            new StubProvider(_ => new ExternalCapabilityReceipt(
                "game.purchase.prepare", true, true, evidence.RootElement.Clone(), null)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"confirmationId\":\"confirm_test\",\"expectedPriceCents\":100}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Irreversible));
        });
    }

    [Test]
    public async Task AmbiguousExternalEffectIsPropagatedToRecoveryPolicy()
    {
        var handler = new ExternalCapabilityHandler(
            "message.send",
            new StubProvider(operation => new ExternalCapabilityReceipt(
                operation,
                true,
                false,
                null,
                "message_delivery_not_verified")));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"recipientId\":\"recipient_test\",\"text\":\"Hola\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.CauseCode, Is.EqualTo("external_effect_ambiguous"));
        });
    }

    [Test]
    public async Task UnobservedPostDispatchAmbiguityIsPropagatedToRecoveryPolicy()
    {
        var handler = new ExternalCapabilityHandler(
            "message.send",
            new StubProvider(operation => new ExternalCapabilityReceipt(
                operation,
                false,
                false,
                null,
                "message_delivery_receipt_lost")
            {
                EffectMayHaveOccurred = true,
            }));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"recipientId\":\"recipient_test\",\"text\":\"Hola\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.CauseCode, Is.EqualTo("external_effect_ambiguous"));
            Assert.That(outcome.ErrorCode, Is.EqualTo("message_delivery_receipt_lost"));
        });
    }

    [Test]
    public async Task ProviderExceptionBecomesStableFailureAndTheBoundaryRemainsUsable()
    {
        using JsonDocument evidence = JsonDocument.Parse(
            """{"version":1,"source":"recovered_test_provider"}""");
        var provider = new SequencedProvider(
            new InvalidDataException("simulated provider contract mismatch"),
            new ExternalCapabilityReceipt(
                "game.install.status",
                false,
                true,
                evidence.RootElement.Clone(),
                null));
        var handler = new ExternalCapabilityHandler("game.install.status", provider);

        OperationOutcome failed = await handler.ExecuteAsync(
            Invocation("""{"appId":"620"}"""),
            CancellationToken.None);
        OperationOutcome recovered = await handler.ExecuteAsync(
            Invocation("""{"appId":"620"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(failed.Succeeded, Is.False);
            Assert.That(failed.Verified, Is.False);
            Assert.That(failed.ErrorCode, Is.EqualTo("external_provider_failed"));
            Assert.That(failed.EffectMayHaveOccurred, Is.False);
            Assert.That(recovered.Succeeded, Is.True);
            Assert.That(recovered.Verified, Is.True);
            Assert.That(provider.Calls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task ProviderExceptionOnMutatingOperationRemainsConservativelyAmbiguous()
    {
        var handler = new ExternalCapabilityHandler(
            "message.send",
            new ThrowingProvider(new IOException("simulated transport failure")));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"recipientId":"recipient_test","text":"hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("external_provider_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.CauseCode, Is.EqualTo("external_effect_ambiguous"));
        });
    }

    [Test]
    public async Task ProductionGateNeverClaimsSuccessWithoutOfficialAdapter()
    {
        var provider = new WindowsExternalCapabilityProvider();
        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "vision.describe",
            Invocation("{\"captureId\":\"capture_test\"}").Arguments,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result, Is.Null);
            Assert.That(receipt.ErrorCode, Is.Not.Null.And.Not.Empty);
        });
    }

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"), JsonDocument.Parse(json).RootElement.Clone());

    private sealed class StubProvider(Func<string, ExternalCapabilityReceipt> result)
        : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result(operation));
        }
    }

    private sealed class SequencedProvider(
        Exception first,
        ExternalCapabilityReceipt second) : IExternalCapabilityProvider
    {
        public int Calls { get; private set; }

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Calls++;
            return Calls == 1
                ? ValueTask.FromException<ExternalCapabilityReceipt>(first)
                : ValueTask.FromResult(second);
        }
    }

    private sealed class ThrowingProvider(Exception exception) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromException<ExternalCapabilityReceipt>(exception);
        }
    }
}
