using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// When a turn of the native tool loop takes no more calls (src/Baxy.App/TurnClosing.cs, linked here: the App has no
/// test project).
/// </summary>
[TestFixture]
public sealed class TurnClosingTests
{
    private static readonly TimeSpan Soon = TimeSpan.FromSeconds(5);

    [Test]
    public void DifferentCallsInTimeKeepTheTurnOpenUntilTheMoveCap()
    {
        var closing = new TurnClosing();
        for (int call = 1; call < TurnClosing.MaximumModelCalls; call++)
        {
            Assert.That(closing.AfterCall(call, Soon, "web.fetch", $"{{\"url\":\"https://a.example/{call}\"}}",
                Result("completed")), Is.False, $"call {call}");
        }

        Assert.That(closing.AfterCall(TurnClosing.MaximumModelCalls, Soon, "web.fetch", "{\"url\":\"https://b.example\"}",
            Result("completed")), Is.True);
    }

    // E5: four app.open of a console app, each verification_failed after 30 s, and no answer in time. After two the
    // model may still change course (e2e E011: two calculator_window_not_found, then app.open): the third closes it.
    [Test]
    public void TheSameFailedCallThreeTimesClosesTheTurnTwiceDoesNot()
    {
        var closing = new TurnClosing();
        Assert.That(closing.AfterCall(1, Soon, "app.open", "{\"appId\":\"cmd\"}",
            Result("failed", "verification_failed")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "app.open", "{\"appId\":\"cmd\"}",
            Result("failed", "verification_failed")), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"cmd\"}",
            Result("failed", "verification_failed")), Is.True);
    }

    // E022: the same page fetched eight times until the results overflowed the context.
    [Test]
    public void TheSameCompletedCallThreeTimesClosesTheTurn()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://www.rfc-editor.org/info/rfc2324/\"}";
        Assert.That(closing.AfterCall(1, Soon, "web.fetch", page, Result("completed")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "web.fetch", page, Result("completed")), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "web.fetch", page, Result("completed")), Is.True);
    }

    [Test]
    public void AFailureWithOtherArgumentsOrAnotherOutcomeIsANewTry()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "app.open", "{\"appId\":\"cmd\"}",
                Result("failed", "verification_failed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "app.open", "{\"appId\":\"terminal\"}",
                Result("failed", "verification_failed")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"terminal\"}",
                Result("failed", "launch_failed")), Is.False);
            // The first call again: its second appearance in the turn, not yet the third.
            Assert.That(closing.AfterCall(4, Soon, "app.open", "{\"appId\":\"cmd\"}",
                Result("failed", "verification_failed")), Is.False);
        });
    }

    // Feria 2026-10-27: a navigation and a new tab alternated 16 times in 55 s with no answer, up to the move cap; each
    // call broke the other's run. The same call with the same result a third time in the turn closes it, in a row or not.
    [Test]
    public void TwoCallsThatAlternateCloseTheTurnAtTheThirdAppearance()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://a.example/\"}";
        const string tab = "{\"action\":\"new_tab\"}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "browser.navigate", page, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "browser.control", tab, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "browser.navigate", page, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(4, Soon, "browser.control", tab, Result("completed")), Is.False);
            Assert.That(closing.AfterCall(5, Soon, "browser.navigate", page, Result("completed")), Is.True);
        });
    }

    // E011 (base 0be0f9de9): two calculator_window_not_found, then app.open and the sum. Counting over the whole turn
    // keeps it: the failure appeared twice, and the sum that completes is another result.
    [Test]
    public void TwoEqualFailuresThenAnotherCallAndTheSameCallCompletingKeepTheTurnOpen()
    {
        var closing = new TurnClosing();
        const string sum = "{\"expression\":\"2+2\"}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "calculator.expression.evaluate", sum,
                Result("failed", "calculator_window_not_found")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "calculator.expression.evaluate", sum,
                Result("failed", "calculator_window_not_found")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"calculator\"}", Result("completed")),
                Is.False);
            Assert.That(closing.AfterCall(4, Soon, "calculator.expression.evaluate", sum, Result("completed")),
                Is.False);
        });
    }

    [Test]
    public void AWaitingConfirmationIsNotAFailureToRepeat()
    {
        var closing = new TurnClosing();
        Assert.That(closing.AfterCall(1, Soon, "shell.command.run", "{\"command\":\"python --version\"}",
            Result("pending", "confirmation_required")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "shell.command.run", "{\"command\":\"python --version\"}",
            Result("pending", "confirmation_required")), Is.False);
    }

    [Test]
    public void TheTurnsTimeClosesIt()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, TurnClosing.Budget - TimeSpan.FromSeconds(1), "app.open",
                "{\"appId\":\"steam\"}", Result("completed")), Is.False);
            Assert.That(closing.AfterCall(2, TurnClosing.Budget, "input.text.type", "{\"text\":\"hola\"}",
                Result("completed")), Is.True);
        });
    }

    // Al máximo 7.7: three looks at a window that is still loading, each with another view, are three results: the turn
    // went on (before, the third closed it and the model read «same result»).
    [Test]
    public void TheSameCallWithAnotherResultIsNotARepeat()
    {
        var closing = new TurnClosing();
        const string look = "{\"application\":\"steam\"}";
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "input.visible.controls", look, View("Cargando…")), Is.False);
            Assert.That(closing.AfterCall(2, Soon, "input.visible.controls", look, View("Biblioteca")), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "input.visible.controls", look, View("Biblioteca · Tienda")),
                Is.False);
        });
    }

    [Test]
    public void TheSameCallWithTheSameResultThreeTimesClosesTheTurn()
    {
        var closing = new TurnClosing();
        const string look = "{\"application\":\"steam\"}";
        Assert.That(closing.AfterCall(1, Soon, "input.visible.controls", look, View("Cargando…")), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "input.visible.controls", look, View("Cargando…")), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "input.visible.controls", look, View("Cargando…")), Is.True);
    }

    // How long a call took is not its result: the same console output thrice, each in its own time, is a repeat.
    [Test]
    public void TheTimeACallTookIsNotPartOfItsResult()
    {
        var closing = new TurnClosing();
        const string command = "{\"command\":\"python --version\"}";
        Assert.That(closing.AfterCall(1, Soon, "shell.command.run", command, ConsoleRun(812)), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "shell.command.run", command, ConsoleRun(790)), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "shell.command.run", command, ConsoleRun(805)), Is.True);
    }

    // Holdout v4 (the Steam library, «Biblioteca» 7 times): the click's own count of its unchanged repeats, and the «next»
    // it brings, differ on each repeat and are not its result: the same unchanged click thrice still closes the turn.
    [Test]
    public void AClicksCountOfItsUnchangedRepeatsIsNotPartOfItsResult()
    {
        var closing = new TurnClosing();
        const string click = "{\"label\":\"Biblioteca\"}";
        const string first = "{\"status\":\"failed\",\"error\":\"visible_button_postread_unchanged\"}";
        string Again(int times) => "{\"status\":\"failed\",\"error\":\"visible_button_postread_unchanged\","
            + $"\"observed\":{{\"unchangedInARow\":{times},\"next\":\"changed nothing {times} times\"}}}}";
        Assert.That(closing.AfterCall(1, Soon, "input.visible.click", click, first), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "input.visible.click", click, Again(2)), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "input.visible.click", click, Again(3)), Is.True);
    }

    // Holdout v5 (en vivo, «maximiza Paint»): the same window read 13 times, each with a new single-use windowId
    // (WindowsWindowControlProvider.Issue): the handle is not part of the result, the same read thrice closes the turn.
    [Test]
    public void AWindowsSingleUseHandleIsNotPartOfItsResult()
    {
        var closing = new TurnClosing();
        const string paint = "{\"applicationName\":\"Paint\"}";
        string Read(char digit) => "{\"status\":\"completed\",\"observed\":{\"windows\":[{\"windowId\":\"win_"
            + new string(digit, 32) + "\",\"state\":\"maximized\"}]}}";
        Assert.That(closing.AfterCall(1, Soon, "window.resolve", paint, Read('0')), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "window.resolve", paint, Read('1')), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "window.resolve", paint, Read('a')), Is.True);
    }

    private static string Result(string status, string? error = null) =>
        error is null ? $"{{\"status\":\"{status}\"}}" : $"{{\"status\":\"{status}\",\"error\":\"{error}\"}}";

    private static string View(string text) =>
        $"{{\"status\":\"completed\",\"view\":\"window 1 Steam\\n{text}\"}}";

    private static string ConsoleRun(int milliseconds) =>
        "{\"status\":\"completed\",\"observed\":{\"exitCode\":9009,\"stdout\":\"\",\"durationMs\":"
        + milliseconds + ",\"effectReadBack\":false}}";
}
