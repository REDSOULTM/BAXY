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
            Assert.That(unobserved.Verified, Is.False);
            Assert.That(unobserved.ErrorCode, Is.EqualTo("external_verification_failed"));
            Assert.That(unobserved.CauseCode, Is.EqualTo("external_effect_unobserved"));
            Assert.That(unobserved.EffectMayHaveOccurred, Is.False);
        });
    }

    // Auditoría del Core (w8): that failure dropped the provider's verified post-read; it keeps it now, marked
    // effectObserved:false, with the status, code and uncertainty as they were.
    [Test]
    public async Task AnUnobservedEffectKeepsTheVerifiedPostReadAsFacts()
    {
        OperationOutcome unobserved = await Handle(ExternalJson.Success(
            "wifi.disconnect", Json("""{"version":1,"connected":true,"ssid":"Casa"}"""), effectObserved: false));

        Assert.Multiple(() =>
        {
            Assert.That(unobserved.Succeeded, Is.False);
            Assert.That(unobserved.CauseCode, Is.EqualTo("external_effect_unobserved"));
            Assert.That(unobserved.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(unobserved.Result?.GetProperty("ssid").GetString(), Is.EqualTo("Casa"));
            Assert.That(unobserved.Result?.GetProperty("effectObserved").GetBoolean(), Is.False);
            Assert.That(unobserved.Result?.TryGetProperty("changed", out _), Is.False);
        });
    }

    // Contracase: a result that says effectObserved itself keeps its own, never a second key.
    [Test]
    public async Task AnUnobservedResultThatSaysItselfKeepsItsOwn()
    {
        OperationOutcome unobserved = await Handle(ExternalJson.Success(
            "wifi.disconnect", Json("""{"connected":true,"effectObserved":false}"""), effectObserved: false));

        Assert.That(unobserved.Result?.GetRawText(), Is.EqualTo("""{"connected":true,"effectObserved":false}"""));
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
        string message = await CalculatorMessage("""{"ok":false,"error":"calculator_mode_not_supported"}""");
        using JsonDocument facts = JsonDocument.Parse(message);

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("calculator_mode_not_supported"));
            Assert.That(facts.RootElement.TryGetProperty("observed", out _), Is.False);
        });
    }

    // Holdout v5 V5E021 («a lo que tiene la calculadora súmale 53»): «+53» was refused as invalid, and «53+53» cleared
    // the 47 the person had there without saying so. An expression that starts with an operator continues from the
    // number shown and the receipt says which number; one that starts with a number says what the clear removed.
    [Test]
    public async Task AnExpressionStartingWithAnOperatorContinuesFromTheNumberShown()
    {
        OperationOutcome outcome = await Calculator(
            """{"ok":true,"continued":true,"before":"47","mode":"standard","displayName":"Se muestra 100","expressionName":"47 + 53=","value":"100"}""",
            "+ 53");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            JsonElement result = outcome.Result!.Value;
            Assert.That(result.GetProperty("expression").GetString(), Is.EqualTo("+53"));
            Assert.That(result.GetProperty("startedFrom").GetString(), Is.EqualTo("47"));
            Assert.That(result.TryGetProperty("clearedDisplay", out _), Is.False);
            Assert.That(result.GetProperty("mode").GetString(), Is.EqualTo("standard"));
            Assert.That(result.GetProperty("value").GetString(), Is.EqualTo("100"));
        });
    }

    // Contracaso: an expression that starts with a number clears the display first, and says what it held.
    [Test]
    public async Task AnExpressionStartingWithANumberSaysWhatTheClearRemoved()
    {
        OperationOutcome outcome = await Calculator(
            """{"ok":true,"continued":false,"before":"47","mode":"standard","displayName":"Se muestra 106","expressionName":"53 + 53=","value":"106"}""",
            "53+53");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            JsonElement result = outcome.Result!.Value;
            Assert.That(result.GetProperty("clearedDisplay").GetString(), Is.EqualTo("47"));
            Assert.That(result.TryGetProperty("startedFrom", out _), Is.False);
        });
    }

    // Holdout v5 V5E029 («calcula 2 elevado a 10» in Scientific mode): «2^10» was refused before reaching the keypad.
    // ^ and parentheses go to the keypad (its Scientific buttons), and the receipt says the mode it was pressed in.
    [TestCase("2^10")]
    [TestCase("(1+2)*3")]
    [TestCase("2*(3+4)")]
    public async Task PowerAndParenthesesReachTheKeypadAndTheReceiptSaysTheMode(string expression)
    {
        OperationOutcome outcome = await Calculator(
            """{"ok":true,"continued":false,"before":"0","mode":"scientific","displayName":"Se muestra 1.024","expressionName":"2 ^ 10=","value":"1.024"}""",
            expression);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("mode").GetString(), Is.EqualTo("scientific"));
        });
    }

    // Holdout v5 V5E029: calculator_expression_invalid came with no word of what was wrong. It says which characters
    // were refused (none, when only the shape was wrong) and what is accepted: facts, nothing pressed.
    [TestCase("2%3", "%")]
    [TestCase("x²+1", "x²")]
    [TestCase("2++3", null)]
    [TestCase("(2+3", null)]
    public async Task AnInvalidExpressionSaysWhatWasRefusedAndWhatIsAccepted(string expression, string? refused)
    {
        string message = OperationVisibleFacts.FromOutcome(
            "calculator.expression.evaluate", await Calculator("""{"ok":true}""", expression));
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement root = facts.RootElement;

        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("error").GetString(), Is.EqualTo("calculator_expression_invalid"));
            Assert.That(root.TryGetProperty("effectUncertain", out _), Is.False);
            JsonElement observed = root.GetProperty("observed");
            Assert.That(observed.TryGetProperty("refused", out JsonElement shown) ? shown.GetString() : null, Is.EqualTo(refused));
            Assert.That(observed.GetProperty("accepted").GetString(), Does.Contain("^"));
        });
    }

    // Holdout v5 V5E021 («a lo que tiene la calculadora súmale 53», Calculator showing 47): in 7 of 7 runs that wrote
    // «53» it was refused with only what is accepted, and the model asked the person «¿qué número está en la
    // calculadora?». One number alone says it computes nothing, that nothing was pressed, and the same number with an
    // operator before it, which continues from the display as it is; another shape says nothing of the kind.
    [TestCase("53", "+53")]
    [TestCase(" 4,5 ", "+4.5")]
    [TestCase("2++3", null)]
    [TestCase("5 3", null)]
    [TestCase("53+", null)]
    public async Task ANumberAloneSaysAnOperatorBeforeItContinuesFromTheDisplay(string expression, string? continued)
    {
        string message = OperationVisibleFacts.FromOutcome(
            "calculator.expression.evaluate", await Calculator("""{"ok":true}""", expression));
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement observed = facts.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("calculator_expression_invalid"));
            Assert.That(observed.TryGetProperty("next", out JsonElement next) ? next.GetString() : null, continued is null
                ? Is.Null
                : Is.EqualTo($"{continued[1..]} alone has no operator: it computes nothing, and nothing was pressed; "
                    + $"{continued} continues from the number the display shows now, without reading it first"));
        });
    }

    // BAXY Renew cu (C14): an empty code from a provider is no code: it becomes the generic one, never «» in the journal
    // (journaled as «», the engine did not start again on that profile).
    [Test]
    public async Task AnEmptyProviderCodeIsNeverTheOutcomesCode()
    {
        OperationOutcome outcome = await Handle(new ExternalCapabilityReceipt("wifi.disconnect", true, false, null, ""));
        Assert.That(outcome.ErrorCode, Is.EqualTo("external_verification_failed"));
    }

    // BAXY Renew cu (C14): Discord's own mute, switched and read back; a switch that did not take says its own code.
    [TestCase("""{"ok":true,"effectObserved":true,"before":0,"value":1}""", true, null)]
    [TestCase("""{"ok":false,"effectObserved":true,"before":0,"value":0}""", false, "client_microphone_postread_failed")]
    [TestCase("""{"ok":false,"effectObserved":false,"error":"client_mute_button_not_found"}""", false, "client_mute_button_not_found")]
    public async Task TheClientsOwnMuteIsSwitchedAndReadBack(string scriptOutput, bool succeeded, string? code)
    {
        const string operation = "client.microphone.set";
        var adapter = new WindowsDeviceControlAdapter(
            Path.GetTempPath(), Path.GetTempPath(), new ScriptedRunner(scriptOutput));
        OperationOutcome outcome = await new ExternalCapabilityHandler(operation, new AdapterProvider(adapter))
            .ExecuteAsync(
                new OperationInvocation("request", "mission", "invocation", Json("""{"client":"discord","muted":true}""")),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(succeeded));
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            if (succeeded)
            {
                Assert.That(outcome.Result!.Value.GetProperty("muted").GetBoolean(), Is.True);
                Assert.That(outcome.Result!.Value.GetProperty("mutedBefore").GetBoolean(), Is.False);
            }
        });
    }

    private static async Task<string> CalculatorMessage(string scriptOutput) =>
        OperationVisibleFacts.FromOutcome("calculator.expression.evaluate", await Calculator(scriptOutput, "6*7"));

    private static async Task<OperationOutcome> Calculator(string scriptOutput, string expression)
    {
        const string operation = "calculator.expression.evaluate";
        var adapter = new WindowsDeviceControlAdapter(
            Path.GetTempPath(), Path.GetTempPath(), new ScriptedRunner(scriptOutput));
        return await new ExternalCapabilityHandler(operation, new AdapterProvider(adapter))
            .ExecuteAsync(
                new OperationInvocation(
                    "request", "mission", "invocation", Json(JsonSerializer.Serialize(new { expression }))),
                CancellationToken.None);
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

    // Al máximo, flujos: what the provider reads of the target before the person is asked becomes the invocation's end
    // only as a failure before any effect; anything else leaves the call to ask and run.
    [Test]
    public async Task AReadBeforeTheYesEndsTheCallOnlyAsAFailureBeforeAnyEffect()
    {
        JsonElement walked = Json("""{"searchedFolders":["desktop"]}""");
        var missing = new ExternalCapabilityReceipt("filesystem.known.trash.named", false, false, walked, "known_file_not_found");

        InvocationPreflightResult refused = await Preflight(missing);
        InvocationPreflightResult afterAnEffect = await Preflight(missing with { EffectMayHaveOccurred = true });
        InvocationPreflightResult another = await Preflight(missing with { Operation = "file.read" });
        InvocationPreflightResult nothing = await Preflight(null);

        Assert.Multiple(() =>
        {
            Assert.That(refused.Failure?.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(refused.Failure?.Result?.GetProperty("searchedFolders").GetArrayLength(), Is.EqualTo(1));
            Assert.That(afterAnEffect, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(another, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(nothing, Is.SameAs(InvocationPreflightResult.Proceed));
        });
    }

    private static ValueTask<InvocationPreflightResult> Preflight(ExternalCapabilityReceipt? found) =>
        new ExternalCapabilityHandler("filesystem.known.trash.named", new PreflightProvider(found)).PreflightAsync(
            Json("""{"folder":"desktop","fileName":"viejo.txt"}"""), CancellationToken.None);

    private sealed class PreflightProvider(ExternalCapabilityReceipt? found) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            throw new AssertionException("a read runs nothing");

        public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            ValueTask.FromResult(found);
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
