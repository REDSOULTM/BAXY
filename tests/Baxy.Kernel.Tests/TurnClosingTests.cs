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
                "completed", null), Is.False, $"call {call}");
        }

        Assert.That(closing.AfterCall(TurnClosing.MaximumModelCalls, Soon, "web.fetch", "{\"url\":\"https://b.example\"}",
            "completed", null), Is.True);
    }

    // E5: four app.open of a console app, each verification_failed after 30 s, and no answer in time. After two the
    // model may still change course (e2e E011: two calculator_window_not_found, then app.open): the third closes it.
    [Test]
    public void TheSameFailedCallThreeTimesClosesTheTurnTwiceDoesNot()
    {
        var closing = new TurnClosing();
        Assert.That(closing.AfterCall(1, Soon, "app.open", "{\"appId\":\"cmd\"}", "failed", "verification_failed"),
            Is.False);
        Assert.That(closing.AfterCall(2, Soon, "app.open", "{\"appId\":\"cmd\"}", "failed", "verification_failed"),
            Is.False);
        Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"cmd\"}", "failed", "verification_failed"),
            Is.True);
    }

    // E022: the same page fetched eight times until the results overflowed the context.
    [Test]
    public void TheSameCompletedCallThreeTimesClosesTheTurn()
    {
        var closing = new TurnClosing();
        const string page = "{\"url\":\"https://www.rfc-editor.org/info/rfc2324/\"}";
        Assert.That(closing.AfterCall(1, Soon, "web.fetch", page, "completed", null), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "web.fetch", page, "completed", null), Is.False);
        Assert.That(closing.AfterCall(3, Soon, "web.fetch", page, "completed", null), Is.True);
    }

    [Test]
    public void AFailureWithOtherArgumentsOrAnotherOutcomeIsANewTry()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, Soon, "app.open", "{\"appId\":\"cmd\"}", "failed", "verification_failed"),
                Is.False);
            Assert.That(closing.AfterCall(2, Soon, "app.open", "{\"appId\":\"terminal\"}", "failed",
                "verification_failed"), Is.False);
            Assert.That(closing.AfterCall(3, Soon, "app.open", "{\"appId\":\"terminal\"}", "failed", "launch_failed"),
                Is.False);
            // A call between two equal ones breaks the run: only consecutive repeats count.
            Assert.That(closing.AfterCall(4, Soon, "app.open", "{\"appId\":\"cmd\"}", "failed", "verification_failed"),
                Is.False);
        });
    }

    [Test]
    public void AWaitingConfirmationIsNotAFailureToRepeat()
    {
        var closing = new TurnClosing();
        Assert.That(closing.AfterCall(1, Soon, "shell.command.run", "{\"command\":\"python --version\"}", "pending",
            "confirmation_required"), Is.False);
        Assert.That(closing.AfterCall(2, Soon, "shell.command.run", "{\"command\":\"python --version\"}", "pending",
            "confirmation_required"), Is.False);
    }

    [Test]
    public void TheTurnsTimeClosesIt()
    {
        var closing = new TurnClosing();
        Assert.Multiple(() =>
        {
            Assert.That(closing.AfterCall(1, TurnClosing.Budget - TimeSpan.FromSeconds(1), "app.open",
                "{\"appId\":\"steam\"}", "completed", null), Is.False);
            Assert.That(closing.AfterCall(2, TurnClosing.Budget, "input.text.type", "{\"text\":\"hola\"}",
                "completed", null), Is.True);
        });
    }
}
