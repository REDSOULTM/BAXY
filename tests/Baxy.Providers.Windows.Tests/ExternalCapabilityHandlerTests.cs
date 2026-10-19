using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;
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

    // E011 (pc-ayudas): calculator.expression.evaluate without the Calculator's window failed with its code alone, and
    // the model called it again twice. The failure now says what was seen and that app_open can start it, in the message
    // the model reads (observed.next); nothing was pressed, so nothing may have happened.
    [Test]
    public async Task ACalculatorWithoutItsWindowSaysSoAndThatAppOpenCanStartIt()
    {
        string message = await CalculatorMessage("""{"ok":false,"error":"calculator_window_not_found"}""");
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement root = facts.RootElement;

        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("status").GetString(), Is.EqualTo("failed"));
            Assert.That(root.GetProperty("error").GetString(), Is.EqualTo("calculator_window_not_found"));
            Assert.That(root.TryGetProperty("effectUncertain", out _), Is.False);
            Assert.That(root.GetProperty("observed").GetProperty("next").GetString(), Is.EqualTo(
                "no Calculator window is open and nothing was pressed; app_open can start the Calculator, then this "
                + "expression can be evaluated again"));
        });
    }

    // With the aid off (BAXY_AYUDAS=none) the failure is the one of the starting product: its code and no hint.
    [Test]
    public async Task ACalculatorWithoutItsWindowWithTheAidOffCarriesNoHint()
    {
        using IDisposable off = ModelAids.Use("none");
        string message = await CalculatorMessage("""{"ok":false,"error":"calculator_window_not_found"}""");
        using JsonDocument facts = JsonDocument.Parse(message);

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("calculator_window_not_found"));
            Assert.That(facts.RootElement.TryGetProperty("observed", out JsonElement observed)
                && observed.TryGetProperty("next", out _), Is.False);
        });
    }

    // Contracaso: another failure of the Calculator (its keypad in another mode) carries no such hint.
    [Test]
    public async Task ACalculatorInAnotherModeCarriesNoAppOpenHint()
    {
        string message = await CalculatorMessage("""{"ok":false,"error":"calculator_mode_not_standard"}""");
        using JsonDocument facts = JsonDocument.Parse(message);

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("calculator_mode_not_standard"));
            Assert.That(facts.RootElement.TryGetProperty("observed", out _), Is.False);
        });
    }

    private static async Task<string> CalculatorMessage(string scriptOutput)
    {
        const string operation = "calculator.expression.evaluate";
        var adapter = new WindowsDeviceControlAdapter(
            Path.GetTempPath(), Path.GetTempPath(), new ScriptedRunner(scriptOutput));
        OperationOutcome outcome = await new ExternalCapabilityHandler(operation, new AdapterProvider(adapter))
            .ExecuteAsync(
                new OperationInvocation("request", "mission", "invocation", Json("""{"expression":"6*7"}""")),
                CancellationToken.None);
        return OperationVisibleFacts.FromOutcome(operation, outcome);
    }

    private sealed class ScriptedRunner(string output) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
    }

    private sealed class AdapterProvider(WindowsDeviceControlAdapter adapter) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            adapter.InvokeAsync(operation, arguments, cancellationToken);
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
