using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 80: calculator.expression.evaluate with no Calculator open opens it by app.open and presses the expression
/// there; the result says it was opened. A Calculator already open is never opened again.
/// </summary>
[TestFixture]
public sealed class CalculatorOpeningHandlerTests
{
    private const string Shown = """{"value":"444","display":"La pantalla muestra 444"}""";
    private const string Verified = """{"displayName":"Calculadora","windowId":"w1","window":77}""";

    [Test]
    public async Task WithNoneOpenItOpensItselfAndPressesTheSameExpression()
    {
        var evaluate = new Scripted(NotOpen(), OperationOutcome.Success(Element(Shown)));
        var opening = new List<JsonElement>();

        OperationOutcome outcome = await Handler(evaluate, (invocation, _) =>
        {
            opening.Add(invocation.Arguments.Clone());
            return ValueTask.FromResult(OperationOutcome.Success(Element(Verified)));
        }).ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result?.GetProperty("value").GetString(), Is.EqualTo("444"));
            Assert.That(outcome.Result?.GetProperty("applicationOpened").GetString(), Is.EqualTo("Calculadora"));
            Assert.That(outcome.Result?.GetProperty("windowId").GetString(), Is.EqualTo("w1"));
            Assert.That(outcome.Result?.GetProperty("window").GetInt64(), Is.EqualTo(77));
            Assert.That(opening, Has.Count.EqualTo(1));
            Assert.That(opening[0].GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(opening[0].GetProperty("forControl").GetBoolean(), Is.True);
            Assert.That(evaluate.Arguments, Is.EqualTo(new[] { """{"expression":"37*12"}""", """{"expression":"37*12"}""" }));
        });
    }

    [Test]
    public async Task AlreadyOpenItIsNeverOpenedAgain()
    {
        var evaluate = new Scripted(OperationOutcome.Success(Element(Shown)));
        int openings = 0;

        OperationOutcome outcome = await Handler(evaluate, (_, _) =>
        {
            openings++;
            return ValueTask.FromResult(OperationOutcome.Success(Element(Verified)));
        }).ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result?.GetRawText(), Is.EqualTo(Shown));
            Assert.That(openings, Is.Zero);
            Assert.That(evaluate.Arguments, Has.Count.EqualTo(1));
        });
    }

    // Another refusal of an open Calculator (its keypad in another mode) is the Calculator's own answer.
    [Test]
    public async Task AnotherFailureOpensNothing()
    {
        var evaluate = new Scripted(OperationOutcome.Failure("calculator_mode_not_supported"));
        int openings = 0;

        OperationOutcome outcome = await Handler(evaluate, (_, _) =>
        {
            openings++;
            return ValueTask.FromResult(OperationOutcome.Success(Element(Verified)));
        }).ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("calculator_mode_not_supported"));
            Assert.That(openings, Is.Zero);
        });
    }

    // The frame app.open verified shows before its keypad: a refusal from before any press is asked again.
    [Test]
    public async Task AKeypadThatIsNotDrawnYetIsWaitedFor()
    {
        var evaluate = new Scripted(
            NotOpen(), NotOpen(), OperationOutcome.Failure("calculator_button_not_found"),
            OperationOutcome.Success(Element(Shown)));

        OperationOutcome outcome = await Handler(evaluate, Opens).ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(evaluate.Arguments, Has.Count.EqualTo(4));
        });
    }

    // A failure that may come after a press is never pressed again, and it says the Calculator was opened.
    [Test]
    public async Task AFailureAfterTheOpeningSaysItWasOpenedAndIsNotPressedAgain()
    {
        var evaluate = new Scripted(NotOpen(), OperationOutcome.Failure("calculator_display_not_verified"));

        OperationOutcome outcome = await Handler(evaluate, Opens).ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("calculator_display_not_verified"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.Result?.GetProperty("applicationOpened").GetString(), Is.EqualTo("Calculadora"));
            Assert.That(evaluate.Arguments, Has.Count.EqualTo(2));
        });
    }

    // A keypad that never comes ends with the budget; the next that says to open it is gone, it has just been opened.
    [Test]
    public async Task AWindowThatNeverComesEndsWithoutSayingToOpenItAgain()
    {
        var evaluate = new Scripted(NotOpen());

        OperationOutcome outcome = await Handler(evaluate, Opens, TimeSpan.Zero)
            .ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("calculator_window_not_found"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.Result?.TryGetProperty("next", out _), Is.False);
            Assert.That(outcome.Result?.GetProperty("applicationOpened").GetString(), Is.EqualTo("Calculadora"));
        });
    }

    // Its package's name first, then the classic Calculator's: a Windows with neither keeps the failure and its next.
    [Test]
    public async Task WithNoCalculatorInstalledTheFailureKeepsItsNextAndNothingWasPressed()
    {
        var evaluate = new Scripted(NotOpen());
        var asked = new List<string?>();

        OperationOutcome outcome = await Handler(evaluate, (invocation, _) =>
        {
            asked.Add(invocation.Arguments.GetProperty("appId").GetString());
            return ValueTask.FromResult(OperationOutcome.Failure("app_not_found"));
        }).ExecuteAsync(Invocation(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("calculator_window_not_found"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result?.GetProperty("next").GetString(), Is.EqualTo("app_open first"));
            Assert.That(asked, Is.EqualTo(new[] { "Microsoft.WindowsCalculator", "Calculator" }));
            Assert.That(evaluate.Arguments, Has.Count.EqualTo(1));
        });
    }

    private static CalculatorOpeningHandler Handler(
        IOperationHandler evaluate,
        Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open,
        TimeSpan? budget = null) =>
        new(evaluate, open, budget, static (_, _) => ValueTask.CompletedTask);

    private static ValueTask<OperationOutcome> Opens(OperationInvocation invocation, CancellationToken token) =>
        ValueTask.FromResult(OperationOutcome.Success(Element(Verified)));

    private static OperationOutcome NotOpen() =>
        OperationOutcome.Failure("calculator_window_not_found", result: Element("""{"next":"app_open first"}"""));

    private static OperationInvocation Invocation() =>
        new("request", "mission", "invocation", Element("""{"expression":"37*12"}"""));

    private static JsonElement Element(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.Clone();
    }

    private sealed class Scripted(params OperationOutcome[] outcomes) : IOperationHandler
    {
        public List<string> Arguments { get; } = [];

        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("calculator.expression.evaluate");

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
        {
            Arguments.Add(invocation.Arguments.GetRawText());
            return ValueTask.FromResult(outcomes[Math.Min(Arguments.Count, outcomes.Length) - 1]);
        }
    }
}
