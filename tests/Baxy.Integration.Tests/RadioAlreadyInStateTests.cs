using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// v3 r6 lectores (t2-r4 c15 «turn bluetooth on, gonna connect my headphones» → «the change could not be observed»):
/// the radio was already on, the adapter skipped it and its post-read showed it on, and the handler turned that into
/// external_effect_unobserved. A verified post-read already in the requested state is the request done with
/// changed:false; a radio that does not reach the state, or a receipt with no verified state, still fails.
/// </summary>
[TestFixture]
public sealed class RadioAlreadyInStateTests
{
    [TestCase("bluetooth.radio.set")]
    [TestCase("wifi.radio.set")]
    public async Task ARadioAlreadyInTheRequestedStateIsDoneWithoutAChange(string operation)
    {
        using JsonDocument evidence = JsonDocument.Parse(
            """{"version":1,"state":true,"changed":false,"radioCount":1,"authority":"windows_radio_api_postread"}""");
        var handler = new ExternalCapabilityHandler(operation, new Stub(name =>
            new ExternalCapabilityReceipt(name, EffectObserved: false, Verified: true, evidence.RootElement.Clone(), null)
            {
                StateAlreadyReached = true,
            }));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.ProductDescriptor!.RequiresObservedEffect, Is.True);
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
        });
    }

    [Test]
    public async Task AVerifiedSwitchWithNeitherAnEffectNorTheStateStillFails()
    {
        // Contracaso: the old contract holds for a receipt that proves nothing.
        using JsonDocument evidence = JsonDocument.Parse("""{"version":1}""");
        var handler = new ExternalCapabilityHandler("bluetooth.radio.set", new Stub(name =>
            new ExternalCapabilityReceipt(name, EffectObserved: false, Verified: true, evidence.RootElement.Clone(), null)));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.CauseCode, Is.EqualTo("external_effect_unobserved"));
        });
    }

    [Test]
    public async Task AnAlreadyReachedClaimAfterACrossedBoundaryIsNotTrusted()
    {
        using JsonDocument evidence = JsonDocument.Parse("""{"version":1,"state":true,"changed":false}""");
        var handler = new ExternalCapabilityHandler("bluetooth.radio.set", new Stub(name =>
            new ExternalCapabilityReceipt(name, EffectObserved: false, Verified: true, evidence.RootElement.Clone(), null)
            {
                StateAlreadyReached = true,
                EffectMayHaveOccurred = true,
            }));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"state":true}"""), CancellationToken.None);

        Assert.That(outcome.Succeeded, Is.False);
    }

    [Test]
    public async Task ARadioThatDoesNotReachTheStateStillFails()
    {
        // Contracaso: an off radio that does not change is the adapter's post-read failure, never «already».
        var handler = new ExternalCapabilityHandler("bluetooth.radio.set", new Stub(name =>
            new ExternalCapabilityReceipt(name, EffectObserved: false, Verified: false, null,
                "bluetooth_radio_postread_failed")));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("bluetooth_radio_postread_failed"));
        });
    }

    private static OperationInvocation Invocation(string arguments) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(arguments).RootElement.Clone());

    private sealed class Stub(Func<string, ExternalCapabilityReceipt> receipt) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken) =>
            ValueTask.FromResult(receipt(operation));
    }
}
