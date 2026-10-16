using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// When BAXY's line is the confirmation of the call that waits (src/Baxy.App/ConfirmationAsk.cs, linked here: the App
/// has no test project).
/// </summary>
[TestFixture]
public sealed class ConfirmationAskTests
{
    [Test]
    public void ACallTheTurnAskedForIsWhatItsLineAsks()
    {
        Assert.That(ConfirmationAsk.Asks(waiting: true, askedAt: 50, turnStarted: 40, personAt: 30), Is.True);
    }

    [Test]
    public void ACallAskedBeforeThePersonsWordsIsWhatTheirTurnAnswers()
    {
        Assert.That(ConfirmationAsk.Asks(waiting: true, askedAt: 10, turnStarted: 40, personAt: 30), Is.True);
    }

    [Test]
    public void AHeartbeatsCallHeldWhileThePersonsWordsWaitedIsNotWhatTheirTurnAsks()
    {
        // They spoke at 30, the heartbeat held its call at 35, their turn started at 40: the model never read it.
        Assert.That(ConfirmationAsk.Asks(waiting: true, askedAt: 35, turnStarted: 40, personAt: 30), Is.False);
    }

    [Test]
    public void WithNothingWaitingNoLineIsAConfirmation()
    {
        Assert.That(ConfirmationAsk.Asks(waiting: false, askedAt: 50, turnStarted: 40, personAt: 30), Is.False);
    }
}
