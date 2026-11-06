using System.Text;
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

    // Banco ciego c3 C3-148 (las tres semillas): email.latest.read read and verified the newest mail (sender, subject,
    // body) and the Core turned it into external_effect_unobserved, because its privacy_sensitive risk made it require an
    // observed effect. A verified read of something private changes nothing: it is done. A privacy-sensitive call that
    // changes something still needs its effect seen.
    [Test]
    public async Task AVerifiedPrivateReadIsDoneAndAPrivateChangeStillNeedsItsEffectSeen()
    {
        JsonElement mail = Json("""{"version":1,"sender":"Ana","subject":"Hola","body":"..."}""");
        OperationOutcome read = await new ExternalCapabilityHandler(
                "email.latest.read",
                new FixedProvider(ExternalJson.Success("email.latest.read", mail, effectObserved: false)))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", Json("{}")), CancellationToken.None);
        OperationOutcome connect = await new ExternalCapabilityHandler(
                "wifi.connect",
                new FixedProvider(ExternalJson.Success("wifi.connect", Json("""{"connected":true}"""), effectObserved: false)))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", Json("{}")), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Succeeded && read.Verified, Is.True, read.CauseCode);
            Assert.That(read.Result?.GetProperty("subject").GetString(), Is.EqualTo("Hola"));
            Assert.That(connect.Succeeded, Is.False);
            Assert.That(connect.CauseCode, Is.EqualTo("external_effect_unobserved"));
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
            // Encargo 34: the call that starts it comes first, with its argument written.
            Assert.That(root.GetProperty("observed").GetProperty("next").GetString(), Is.EqualTo(
                "app_open {\"appId\":\"Calculator\"} starts the Calculator, then this expression can be evaluated "
                + "again; this call pressed nothing: no Calculator window is open"));
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

    // Ajuste c3, e2e E011 («suma 250 más 175 y luego multiplica el resultado por 2»): «(250+175)*2» on the Standard
    // keypad failed with calculator_needs_scientific_mode alone, and in 3 runs the model told the person the Calculator
    // could not do it (once after six clicks on its system menu) or pressed the digits by hand; the runs that wrote
    // «250+175*2» got 850 there. The failure now says the mode it read, that nothing was pressed, and how that keypad
    // computes: a fact, never a mode switched nor an expression rewritten for the model.
    [Test]
    public async Task AParenthesisOnTheStandardKeypadSaysHowThatKeypadComputes()
    {
        string message = await CalculatorMessage(
            """{"ok":false,"error":"calculator_needs_scientific_mode","mode":"standard"}""");
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement root = facts.RootElement;

        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("status").GetString(), Is.EqualTo("failed"));
            Assert.That(root.GetProperty("error").GetString(), Is.EqualTo("calculator_needs_scientific_mode"));
            Assert.That(root.TryGetProperty("effectUncertain", out _), Is.False);
            Assert.That(root.GetProperty("observed").GetProperty("mode").GetString(), Is.EqualTo("standard"));
            Assert.That(root.GetProperty("observed").GetProperty("next").GetString(), Is.EqualTo(
                "nothing was pressed: the Calculator is in its Standard mode, whose keypad has no ( ) nor ^ and applies "
                + "each operator in the order pressed, without precedence (2+3*4 gives 20 there); an expression written "
                + "in that order without them is evaluated there"));
        });
    }

    // With the aid off the failure is the one of the starting product: its code and no hint.
    [Test]
    public async Task AParenthesisOnTheStandardKeypadWithTheAidOffCarriesNoHint()
    {
        using IDisposable off = ModelAids.Use("none");
        string message = await CalculatorMessage(
            """{"ok":false,"error":"calculator_needs_scientific_mode","mode":"standard"}""");
        using JsonDocument facts = JsonDocument.Parse(message);

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("calculator_needs_scientific_mode"));
            Assert.That(facts.RootElement.TryGetProperty("observed", out _), Is.False);
        });
    }

    // Auditoría de fallos de la App (e2e del 29 y 30-10, E011): with the hint above the model still had to rewrite an
    // expression that was right, and 7 of the 108 failures of two days of e2e were «(250+175)*2» refused on the Standard
    // keypad (the person told the Calculator could not). BAXY computes an order of the same numbers and operators that
    // the Standard keypad, applying each operator in the order pressed, takes to the value the parentheses mean.
    [TestCase("(250+175)*2", "250+175*2")]
    [TestCase("2*(3+4)", "3+4*2")]
    [TestCase("(2+3*4)*2", "3*4+2*2")]
    [TestCase("(10+2)/4", "10+2/4")]
    [TestCase("((1+2)*3-4)/5", "1+2*3-4/5")]
    [TestCase("(1.5+2)*4", "1.5+2*4")]
    public void AParenthesisedExpressionHasAnOrderTheStandardKeypadComputesTheSame(string keys, string inOrder) =>
        Assert.That(WindowsDeviceControlAdapter.CalculatorStandardOrder(keys), Is.EqualTo(inOrder));

    // Contracases: no such order without the keypad's memory (a group subtracted, divided or two groups multiplied),
    // a power (no ^ there), an expression without parentheses (pressed as written, as before) or one that continues from
    // the number shown.
    [TestCase("10-(2+3)")]
    [TestCase("10/(2+3)")]
    [TestCase("(1+2)*(3+4)")]
    [TestCase("(2+3)^2")]
    [TestCase("2+3*4")]
    [TestCase("*(2+3)")]
    public void AnExpressionWithoutSuchAnOrderHasNone(string keys) =>
        Assert.That(WindowsDeviceControlAdapter.CalculatorStandardOrder(keys), Is.Null);

    // The order goes to the script with the expression, and the receipt keeps the expression as asked and says what
    // the Standard keypad pressed (pressedInOrder) and the value its display shows.
    [Test]
    public async Task TheStandardKeypadPressesTheOrderAndTheReceiptSaysSo()
    {
        var runner = new CapturingRunner("""{"ok":true,"typed":"250+175*2","inOrder":true,"mode":"standard","before":"0","displayName":"Se muestra 850","expressionName":"425 × 2=","value":"850"}""");
        OperationOutcome outcome = await Calculator(runner, "(250+175)*2");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(Encoding.UTF8.GetString(Convert.FromBase64String(runner.Arguments[^1])), Is.EqualTo("250+175*2"));
            Assert.That(outcome.Result?.GetProperty("expression").GetString(), Is.EqualTo("(250+175)*2"));
            Assert.That(outcome.Result?.GetProperty("pressedInOrder").GetString(), Is.EqualTo("250+175*2"));
            Assert.That(outcome.Result?.GetProperty("value").GetString(), Is.EqualTo("850"));
        });
    }

    // Contracase: an expression without parentheses goes as before (no order), and its receipt says none.
    [Test]
    public async Task AnExpressionWithoutParenthesesGoesWithoutAnOrder()
    {
        var runner = new CapturingRunner("""{"ok":true,"typed":"6*7","mode":"standard","before":"0","displayName":"Se muestra 42","expressionName":"6 × 7=","value":"42"}""");
        OperationOutcome outcome = await Calculator(runner, "6*7");

        Assert.Multiple(() =>
        {
            Assert.That(Encoding.UTF8.GetString(Convert.FromBase64String(runner.Arguments[^2])), Is.EqualTo("6*7"));
            Assert.That(outcome.Result?.TryGetProperty("pressedInOrder", out _), Is.False);
        });
    }

    // Banco de uso 2026-11-03 (U14/U15): app_open opened the classic Calculator (win32calc) and the evaluation answered
    // «no Calculator window is open» with it in front. It is pressed there now, and the receipt says on which Calculator
    // and that its mode was not read.
    [Test]
    public async Task TheClassicCalculatorsResultSaysWhichCalculatorItWas()
    {
        OperationOutcome outcome = await Calculator(
            """{"ok":true,"typed":"245+380","mode":"not_read","calculator":"win32calc","before":"0","displayName":"625","expressionName":"","value":"625"}""",
            "245+380");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result?.GetProperty("value").GetString(), Is.EqualTo("625"));
            Assert.That(outcome.Result?.GetProperty("calculator").GetString(), Is.EqualTo("win32calc"));
            Assert.That(outcome.Result?.GetProperty("mode").GetString(), Is.EqualTo("not_read"));
        });
    }

    // Banco de uso 2026-11-03 (U14/U15): an expression whose value depends on the order the classic Calculator's keypad
    // applies the operators in (its mode is not read) pressed nothing; the failure says which Calculator is open and what
    // is pressed there, and with the aid off it is the code alone.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AnOrderDependentExpressionOnTheClassicCalculatorSaysWhatIsPressedThere(bool aid)
    {
        using IDisposable? off = aid ? null : ModelAids.Use("none");
        string message = await CalculatorMessage(
            """{"ok":false,"error":"calculator_mode_not_read","mode":"not_read","calculator":"win32calc"}""");
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement root = facts.RootElement;

        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("error").GetString(), Is.EqualTo("calculator_mode_not_read"));
            Assert.That(root.TryGetProperty("effectUncertain", out _), Is.False);
            Assert.That(root.TryGetProperty("observed", out JsonElement observed), Is.EqualTo(aid));
            if (aid)
            {
                Assert.That(observed.GetProperty("calculator").GetString(), Is.EqualTo("win32calc"));
                Assert.That(observed.GetProperty("next").GetString(), Does.StartWith(
                    "nothing was pressed: the open Calculator is the classic one (win32calc), whose mode is not read")
                    .And.Contain("3*4+2"));
            }
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

    // Feria (caso 14): a root of a number longer than the limit was refused with only its first reason and an «accepted»
    // that said ^ and ( ) worked in Scientific mode, and the model took a root to work there too. The refusal lists every
    // reason that applies, with the numbers over the limit and the limit itself, and never names a mode: no mode takes a
    // function, and whether the keypad has ^ and ( ) is the script's to read.
    [TestCase("√314159265358979323", "√", "characters_not_accepted,no_operator,number_too_long", "314159265358979323")]
    [TestCase("sqrt(314159265358979323)", "sqrt", "characters_not_accepted,no_operator,number_too_long", "314159265358979323")]
    [TestCase("1234567890123+1.1234567", null, "number_too_long", "1234567890123,1.1234567")]
    [TestCase("53", null, "no_operator", null)]
    [TestCase("1+2+3+4+5+6+7+8+9+10", null, "too_many_operators", null)]
    [TestCase("2++3", null, "shape_not_accepted", null)]
    [TestCase("5 3+1", null, "shape_not_accepted", null)]
    [TestCase("123456 7890123+1", null, "shape_not_accepted", null)]
    public async Task AnInvalidExpressionListsEveryReasonAndNamesNoMode(
        string expression, string? refused, string reasons, string? longNumbers)
    {
        string message = OperationVisibleFacts.FromOutcome(
            "calculator.expression.evaluate", await Calculator("""{"ok":true}""", expression));
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement observed = facts.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("calculator_expression_invalid"));
            Assert.That(observed.TryGetProperty("refused", out JsonElement shown) ? shown.GetString() : null, Is.EqualTo(refused));
            Assert.That(observed.GetProperty("reasons").EnumerateArray().Select(reason => reason.GetString()),
                Is.EqualTo(reasons.Split(',')));
            Assert.That(observed.TryGetProperty("longNumbers", out JsonElement numbers)
                ? string.Join(",", numbers.EnumerateArray().Select(number => number.GetString())) : null, Is.EqualTo(longNumbers));
            Assert.That(observed.TryGetProperty("maxDigits", out JsonElement digits) ? digits.GetInt32() : (int?)null,
                Is.EqualTo(longNumbers is null ? null : 12));
            Assert.That(observed.TryGetProperty("maxDecimals", out JsonElement decimals) ? decimals.GetInt32() : (int?)null,
                Is.EqualTo(longNumbers is null ? null : 6));
            Assert.That(observed.TryGetProperty("maxOperators", out JsonElement operators) ? operators.GetInt32() : (int?)null,
                Is.EqualTo(reasons == "too_many_operators" ? 8 : null));
            Assert.That(observed.GetRawText(), Does.Not.Contain("Scientific").IgnoreCase);
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

    // Uso real 2026-11-03 (G5, «ensordéceme en Discord»): with no operation for what the person hears from the call, the
    // model muted Discord's microphone and then Windows' one. Discord's own «Ensordecer» button (UIA Toggle, read live
    // on the PC: «Silenciar» and «Ensordecer», both Toggle) is switched by the same script as the microphone, told which
    // button, and read back; the receipt says both final states, since deafening also mutes the microphone.
    [TestCase("""{"ok":true,"effectObserved":true,"before":0,"value":1,"micMuted":1,"deafened":1}""", true, null)]
    [TestCase("""{"ok":false,"effectObserved":true,"before":0,"value":0}""", false, "client_deafen_postread_failed")]
    [TestCase("""{"ok":false,"effectObserved":false,"error":"client_deafen_button_not_found"}""", false, "client_deafen_button_not_found")]
    public async Task TheClientsOwnDeafenIsSwitchedAndReadBack(string scriptOutput, bool succeeded, string? code)
    {
        const string operation = "client.deafen.set";
        var runner = new CapturingRunner(scriptOutput);
        var adapter = new WindowsDeviceControlAdapter(Path.GetTempPath(), Path.GetTempPath(), runner);
        OperationOutcome outcome = await new ExternalCapabilityHandler(operation, new AdapterProvider(adapter))
            .ExecuteAsync(
                new OperationInvocation("request", "mission", "invocation", Json("""{"client":"discord","deafened":true}""")),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(succeeded));
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(runner.Arguments.TakeLast(2), Is.EqualTo(new[] { "1", "deafen" }));
            if (succeeded)
            {
                Assert.That(outcome.Result!.Value.GetProperty("deafened").GetBoolean(), Is.True);
                Assert.That(outcome.Result!.Value.GetProperty("deafenedBefore").GetBoolean(), Is.False);
                Assert.That(outcome.Result!.Value.GetProperty("micMuted").GetBoolean(), Is.True);
            }
        });
    }

    // The deafen state asked that was already Discord's is said as such (changed:false), and an argument that is not a
    // yes/no never reaches the window.
    [TestCase("""{"client":"discord","deafened":"yes"}""", false, "client_deafen_arguments_invalid")]
    [TestCase("""{"client":"discord","deafened":false}""", true, null)]
    public async Task TheClientsDeafenTakesOnlyAYesOrNo(string arguments, bool succeeded, string? code)
    {
        const string operation = "client.deafen.set";
        var runner = new CapturingRunner("""{"ok":true,"effectObserved":false,"before":0,"value":0,"micMuted":0,"deafened":0}""");
        var adapter = new WindowsDeviceControlAdapter(Path.GetTempPath(), Path.GetTempPath(), runner);
        OperationOutcome outcome = await new ExternalCapabilityHandler(operation, new AdapterProvider(adapter))
            .ExecuteAsync(new OperationInvocation("request", "mission", "invocation", Json(arguments)), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(succeeded));
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(runner.Arguments, succeeded ? Is.Not.Empty : Is.Empty);
            if (succeeded)
            {
                Assert.That(outcome.Result!.Value.GetProperty("deafened").GetBoolean(), Is.False);
                Assert.That(outcome.Result!.Value.GetProperty("deafenedBefore").GetBoolean(), Is.False);
            }
        });
    }

    // G5: the microphone's receipt also says whether Discord stays deafened, read after the switch (unmuting while
    // deafened undeafens in Discord), so a final never has to guess it from two calls.
    [Test]
    public async Task TheClientsMuteReceiptSaysTheDeafenStateReadAfter()
    {
        const string operation = "client.microphone.set";
        var runner = new CapturingRunner("""{"ok":true,"effectObserved":true,"before":1,"value":0,"micMuted":0,"deafened":0}""");
        var adapter = new WindowsDeviceControlAdapter(Path.GetTempPath(), Path.GetTempPath(), runner);
        OperationOutcome outcome = await new ExternalCapabilityHandler(operation, new AdapterProvider(adapter))
            .ExecuteAsync(
                new OperationInvocation("request", "mission", "invocation", Json("""{"client":"discord","muted":false}""")),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(runner.Arguments.TakeLast(2), Is.EqualTo(new[] { "0", "mute" }));
            Assert.That(outcome.Result!.Value.GetProperty("muted").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("deafened").GetBoolean(), Is.False);
        });
    }

    private static async Task<string> CalculatorMessage(string scriptOutput) =>
        OperationVisibleFacts.FromOutcome("calculator.expression.evaluate", await Calculator(scriptOutput, "6*7"));

    private static Task<OperationOutcome> Calculator(string scriptOutput, string expression) =>
        Calculator(new ScriptedRunner(scriptOutput), expression);

    private static async Task<OperationOutcome> Calculator(IExternalProcessRunner runner, string expression)
    {
        const string operation = "calculator.expression.evaluate";
        var adapter = new WindowsDeviceControlAdapter(Path.GetTempPath(), Path.GetTempPath(), runner);
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

    private sealed class CapturingRunner(string output) : IExternalProcessRunner
    {
        public IReadOnlyList<string> Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Arguments = arguments;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
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
            Json("""{"path":"desktop/viejo.txt"}"""), CancellationToken.None);

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
