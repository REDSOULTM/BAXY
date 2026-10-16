using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ExternalCapabilityHandlerTests
{
    // Ronda B: wifi.disconnect with the network already disconnected returned {connected:false}, the same the model read
    // after a disconnection that happened. The state already reached now reaches it as changed:false.
    [Test]
    public async Task TheStateAlreadyReachedReachesTheModelAsChangedFalse()
    {
        JsonElement disconnected = Json("""{"version":1,"connected":false}""");

        OperationOutcome already = await Handle(ExternalJson.Switched("wifi.disconnect", disconnected, effectObserved: false));
        OperationOutcome happened = await Handle(ExternalJson.Switched("wifi.disconnect", disconnected, effectObserved: true));

        Assert.Multiple(() =>
        {
            Assert.That(already.Succeeded && already.Verified, Is.True, already.ErrorCode);
            Assert.That(already.Result?.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(already.Result?.GetProperty("connected").GetBoolean(), Is.False);
            Assert.That(happened.Succeeded && happened.Verified, Is.True, happened.ErrorCode);
            Assert.That(happened.Result?.TryGetProperty("changed", out _), Is.False);
        });
    }

    // Contracaso: a result that says changed itself keeps its own, never a second key.
    [Test]
    public async Task AResultThatAlreadySaysChangedKeepsItsOwn()
    {
        OperationOutcome already = await Handle(ExternalJson.Switched(
            "wifi.disconnect", Json("""{"connected":false,"changed":false}"""), effectObserved: false));

        Assert.That(already.Result?.GetRawText(), Is.EqualTo("""{"connected":false,"changed":false}"""));
    }

    // Contracaso: no effect and no state already reached is still the request not done.
    [Test]
    public async Task NoEffectAndNoStateReachedIsStillUnobserved()
    {
        OperationOutcome unobserved = await Handle(ExternalJson.Success(
            "wifi.disconnect", Json("""{"connected":false}"""), effectObserved: false));

        Assert.Multiple(() =>
        {
            Assert.That(unobserved.Succeeded, Is.False);
            Assert.That(unobserved.CauseCode, Is.EqualTo("external_effect_unobserved"));
        });
    }

    private static ValueTask<OperationOutcome> Handle(ExternalCapabilityReceipt receipt) =>
        new ExternalCapabilityHandler("wifi.disconnect", new FixedProvider(receipt)).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", Json("{}")), CancellationToken.None);

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed class FixedProvider(ExternalCapabilityReceipt receipt) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            ValueTask.FromResult(receipt);
    }
}
